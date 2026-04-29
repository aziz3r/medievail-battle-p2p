/*
 * reseau.c — Routeur UDP P2P Multi-joueurs (Windows / Mac / Linux)
 *
 * Version 3 : Support multi-pairs (jusqu'à MAX_PEERS joueurs simultanés).
 * Fait le pont entre le jeu Python local et N adversaires distants.
 * Broadcast automatique à tous les pairs connus.
 * Découverte dynamique via messages HELLO/HELLO_ACK.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
    typedef int socklen_t;
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    #include <errno.h>
    typedef int SOCKET;
    #define INVALID_SOCKET -1
    #define SOCKET_ERROR -1
    #define closesocket close
#endif

/* --- Configuration -------------------------------------------------------- */
#define PORT_IPC_IN   5000          /* Le C écoute le Python local ici        */
#define PORT_IPC_OUT  5001          /* Le C renvoie vers le Python local ici  */
#define BUFFER_SIZE   65536         /* Buffer augmenté pour les grosses armées */
#define MAX_PEERS     16            /* Nombre max de pairs simultanés          */
#define PEER_TIMEOUT  30            /* Secondes sans paquet = pair perdu       */
#define ACK_MSG       "{\"type\": \"ack\", \"status\": \"ok\"}"

/* --- Structure d'un pair -------------------------------------------------- */
typedef struct {
    char     ip[64];
    int      port;
    char     player_id[8];   /* "A", "B", "C"... */
    time_t   last_seen;
    int      active;
} Peer;

/* --- Variables de session ------------------------------------------------- */
int    g_local_port_net = 6000;
int    g_port_ipc_in    = 5000;
int    g_port_ipc_out   = 5001;
char   g_my_player_id[8] = "A";     /* ID de ce nœud (passé en argument)    */

Peer   g_peers[MAX_PEERS];
int    g_peer_count = 0;

/* --- Gestion des erreurs -------------------------------------------------- */
static void print_error(const char *msg) {
#ifdef _WIN32
    fprintf(stderr, "[ERREUR] %s : %d\n", msg, WSAGetLastError());
#else
    fprintf(stderr, "[ERREUR] %s : %s\n", msg, strerror(errno));
#endif
}

/* --- Création d'un socket UDP bindé --------------------------------------- */
static SOCKET create_udp_socket(const char *bind_ip, int port) {
    SOCKET sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock == INVALID_SOCKET) {
        print_error("socket()");
        return INVALID_SOCKET;
    }

    int reuse = 1;
#ifdef _WIN32
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, (const char*)&reuse, sizeof(reuse));
#else
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
#endif

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons((u_short)port);
    addr.sin_addr.s_addr = inet_addr(bind_ip);

    if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) == SOCKET_ERROR) {
        print_error("bind()");
        closesocket(sock);
        return INVALID_SOCKET;
    }
    return sock;
}

/* --- Table de pairs : upsert ---------------------------------------------- */
static void upsert_peer(const char *ip, int port, const char *player_id) {
    /* Ne pas s'ajouter soi-même */
    if (strcmp(player_id, g_my_player_id) == 0) return;
    
    for (int i = 0; i < g_peer_count; i++) {
        if (strcmp(g_peers[i].ip, ip) == 0 && g_peers[i].port == port) {
            g_peers[i].last_seen = time(NULL);
            g_peers[i].active    = 1;
            if (player_id[0] != '\0')
                strncpy(g_peers[i].player_id, player_id, 7);
            return;
        }
    }
    if (g_peer_count < MAX_PEERS) {
        strncpy(g_peers[g_peer_count].ip, ip, 63);
        g_peers[g_peer_count].port      = port;
        strncpy(g_peers[g_peer_count].player_id, player_id, 7);
        g_peers[g_peer_count].last_seen = time(NULL);
        g_peers[g_peer_count].active    = 1;
        g_peer_count++;
        printf("[NET] ✅ Nouveau pair : %s:%d (joueur '%s') — Total pairs : %d\n",
               ip, port, player_id, g_peer_count);
    } else {
        fprintf(stderr, "[NET] ⚠️  Table de pairs pleine (MAX_PEERS=%d)\n", MAX_PEERS);
    }
}

/* --- Extraction minimale du player_id depuis un JSON ---------------------- */
/*  Cherche "pid":"X" ou "from":"X" dans le buffer.                           */
static void extract_player_id(const char *buf, char *out, int out_size) {
    out[0] = '\0';
    /* Tente "pid":"?" */
    const char *key1 = "\"pid\":\"";
    const char *p = strstr(buf, key1);
    if (p) {
        p += strlen(key1);
        int i = 0;
        while (*p && *p != '"' && i < out_size - 1)
            out[i++] = *p++;
        out[i] = '\0';
        return;
    }
    /* Tente "from":"?" */
    const char *key2 = "\"from\":\"";
    p = strstr(buf, key2);
    if (p) {
        p += strlen(key2);
        int i = 0;
        while (*p && *p != '"' && i < out_size - 1)
            out[i++] = *p++;
        out[i] = '\0';
    }
}

/* --- Diffusion à tous les pairs actifs ------------------------------------ */
static void broadcast_to_peers(SOCKET sock, const char *buf, int len) {
    time_t now = time(NULL);
    for (int i = 0; i < g_peer_count; i++) {
        if (!g_peers[i].active) continue;

        /* Expiration du pair */
        if (now - g_peers[i].last_seen > PEER_TIMEOUT) {
            printf("[NET] ⏰ Pair expiré : %s:%d (%s)\n",
                   g_peers[i].ip, g_peers[i].port, g_peers[i].player_id);
            g_peers[i].active = 0;
            continue;
        }

        struct sockaddr_in dst;
        memset(&dst, 0, sizeof(dst));
        dst.sin_family      = AF_INET;
        dst.sin_port        = htons((u_short)g_peers[i].port);
        dst.sin_addr.s_addr = inet_addr(g_peers[i].ip);
        sendto(sock, buf, len, 0, (struct sockaddr *)&dst, sizeof(dst));
    }
}

/* --- Envoi d'un HELLO_ACK avec la liste des pairs connus ---------------- */
static void send_hello_ack(SOCKET sock, struct sockaddr_in *dest) {
    /* Construction d'un JSON HELLO_ACK minimal avec la liste de pairs */
    char ack_buf[4096];
    int  offset = 0;

    offset += snprintf(ack_buf + offset, sizeof(ack_buf) - offset,
        "{\"type\":\"HELLO_ACK\",\"from\":\"%s\",\"peers\":[", g_my_player_id);

    int first = 1;
    for (int i = 0; i < g_peer_count; i++) {
        if (!g_peers[i].active) continue;
        if (!first) offset += snprintf(ack_buf + offset, sizeof(ack_buf) - offset, ",");
        offset += snprintf(ack_buf + offset, sizeof(ack_buf) - offset,
            "{\"ip\":\"%s\",\"port\":%d,\"pid\":\"%s\"}",
            g_peers[i].ip, g_peers[i].port, g_peers[i].player_id);
        first = 0;
    }
    /* Inclure soi-même pour que le nouveau pair nous connaisse */
    if (!first) offset += snprintf(ack_buf + offset, sizeof(ack_buf) - offset, ",");
    offset += snprintf(ack_buf + offset, sizeof(ack_buf) - offset,
        "{\"ip\":\"self\",\"port\":%d,\"pid\":\"%s\"}", g_local_port_net, g_my_player_id);

    offset += snprintf(ack_buf + offset, sizeof(ack_buf) - offset, "]}");

    sendto(sock, ack_buf, offset, 0, (struct sockaddr *)dest, sizeof(*dest));
    printf("[NET] 📬 HELLO_ACK envoyé à %s:%d\n",
           inet_ntoa(dest->sin_addr), ntohs(dest->sin_port));
}

/* --- Point d'entrée ------------------------------------------------------- */
int main(int argc, char *argv[]) {
    /*
     * Arguments : [port_local_net] [player_id] [port_ipc_in] [port_ipc_out]
     *             [peer1_ip:port] [peer2_ip:port] ...
     *
     * Exemple hôte (joueur A) :
     *   reseau.exe 6000 A 5000 5001
     *
     * Exemple joueur B (connaît A à 127.0.0.1:6000) :
     *   reseau.exe 6001 B 5002 5003 127.0.0.1:6000
     *
     * Exemple joueur C (connaît A et B) :
     *   reseau.exe 6002 C 5004 5005 127.0.0.1:6000 127.0.0.1:6001
     */
    if (argc >= 2) g_local_port_net = atoi(argv[1]);
    if (argc >= 3) strncpy(g_my_player_id, argv[2], 7);
    if (argc >= 4) g_port_ipc_in  = atoi(argv[3]);
    if (argc >= 5) g_port_ipc_out = atoi(argv[4]);

    /* Pairs initiaux passés en ligne de commande : ip:port */
    for (int i = 5; i < argc && i < 5 + MAX_PEERS; i++) {
        char peer_ip[64] = "127.0.0.1";
        int  peer_port   = 0;
        /* Parsing "ip:port" */
        char *colon = strrchr(argv[i], ':');
        if (colon) {
            int prefix_len = (int)(colon - argv[i]);
            if (prefix_len > 0 && prefix_len < 64) {
                strncpy(peer_ip, argv[i], prefix_len);
                peer_ip[prefix_len] = '\0';
            }
            peer_port = atoi(colon + 1);
        } else {
            peer_port = atoi(argv[i]);
        }
        if (peer_port > 0) {
            /* ID inconnu pour l'instant, sera mis à jour au premier HELLO */
            upsert_peer(peer_ip, peer_port, "?");
        }
    }

#ifdef _WIN32
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        print_error("WSAStartup");
        return 1;
    }
#endif

    SOCKET socket_ipc = create_udp_socket("127.0.0.1", g_port_ipc_in);
    SOCKET socket_net = create_udp_socket("0.0.0.0",   g_local_port_net);

    if (socket_ipc == INVALID_SOCKET || socket_net == INVALID_SOCKET) {
#ifdef _WIN32
        WSACleanup();
#endif
        return 1;
    }

    /* Adresse du Python local (réception des données du réseau) */
    struct sockaddr_in local_python_addr;
    memset(&local_python_addr, 0, sizeof(local_python_addr));
    local_python_addr.sin_family      = AF_INET;
    local_python_addr.sin_port        = htons((u_short)g_port_ipc_out);
    local_python_addr.sin_addr.s_addr = inet_addr("127.0.0.1");

    printf("==================================================\n");
    printf("   ROUTEUR P2P MULTI-JOUEURS (v3)               \n");
    printf("==================================================\n");
    printf("  [NET] Joueur ID      : %s\n", g_my_player_id);
    printf("  [IPC] Port locale    : %d (In) / %d (Out)\n", g_port_ipc_in, g_port_ipc_out);
    printf("  [NET] Ecoute P2P     : %d\n", g_local_port_net);
    printf("  [NET] Pairs connus   : %d\n", g_peer_count);
    for (int i = 0; i < g_peer_count; i++)
        printf("        -> %s:%d\n", g_peers[i].ip, g_peers[i].port);
    printf("==================================================\n\n");

    char buffer[BUFFER_SIZE];
    struct sockaddr_in sender_addr;
    socklen_t sender_len;

    /* Envoi d'un HELLO à tous les pairs initiaux pour signaler notre présence */
    {
        char hello_buf[256];
        snprintf(hello_buf, sizeof(hello_buf),
            "{\"type\":\"HELLO\",\"pid\":\"%s\",\"port\":%d}",
            g_my_player_id, g_local_port_net);
        int hello_len = (int)strlen(hello_buf);

        for (int i = 0; i < g_peer_count; i++) {
            struct sockaddr_in dst;
            memset(&dst, 0, sizeof(dst));
            dst.sin_family      = AF_INET;
            dst.sin_port        = htons((u_short)g_peers[i].port);
            dst.sin_addr.s_addr = inet_addr(g_peers[i].ip);
            sendto(socket_net, hello_buf, hello_len, 0, (struct sockaddr *)&dst, sizeof(dst));
        }
        if (g_peer_count > 0)
            printf("[NET] 📢 HELLO envoyé à %d pairs initiaux.\n\n", g_peer_count);
    }

    /* Boucle principale */
    while (1) {
        fd_set read_fds;
        FD_ZERO(&read_fds);
        FD_SET(socket_ipc, &read_fds);
        FD_SET(socket_net, &read_fds);

        int max_fd = (socket_ipc > socket_net) ? (int)socket_ipc : (int)socket_net;
        int ready  = select(max_fd + 1, &read_fds, NULL, NULL, NULL);

        if (ready == SOCKET_ERROR) {
            print_error("select()");
            break;
        }

        /* --- Flux SORTANT : Python -> Réseau (Broadcast) --- */
        if (FD_ISSET(socket_ipc, &read_fds)) {
            sender_len = sizeof(sender_addr);
            int n = recvfrom(socket_ipc, buffer, BUFFER_SIZE - 1, 0,
                             (struct sockaddr *)&sender_addr, &sender_len);
            if (n > 0) {
                buffer[n] = '\0';
                /* Injection du player_id dans le message si absent */
                /* (Le Python doit déjà inclure "pid" dans ses messages) */
                
                int active_peers = 0;
                for (int i = 0; i < g_peer_count; i++)
                    if (g_peers[i].active) active_peers++;

                printf("[IPC->NET] Broadcast vers %d pairs actifs\n", active_peers);
                broadcast_to_peers(socket_net, buffer, n);

                /* ACK au Python */
                sendto(socket_ipc, ACK_MSG, (int)strlen(ACK_MSG), 0,
                       (struct sockaddr *)&sender_addr, sender_len);
            }
        }

        /* --- Flux ENTRANT : Réseau -> Python --- */
        if (FD_ISSET(socket_net, &read_fds)) {
            sender_len = sizeof(sender_addr);
            int n = recvfrom(socket_net, buffer, BUFFER_SIZE - 1, 0,
                             (struct sockaddr *)&sender_addr, &sender_len);
            if (n > 0) {
                buffer[n] = '\0';
                char sender_ip_str[64];
                strncpy(sender_ip_str, inet_ntoa(sender_addr.sin_addr), 63);
                int  sender_port = ntohs(sender_addr.sin_port);

                /* Extraction du player_id depuis le JSON */
                char pid[8] = "";
                extract_player_id(buffer, pid, sizeof(pid));

                /* Auto-découverte : tout paquet entrant = pair potentiel */
                if (pid[0] != '\0') {
                    upsert_peer(sender_ip_str, sender_port, pid);
                }

                /* Traitement spécial HELLO */
                if (strstr(buffer, "\"HELLO\"") || strstr(buffer, "HELLO")) {
                    /* Extraire le port réseau du pair (il déclare son propre port) */
                    const char *port_key = "\"port\":";
                    const char *pp = strstr(buffer, port_key);
                    int declared_port = sender_port;
                    if (pp) {
                        declared_port = atoi(pp + strlen(port_key));
                    }
                    if (pid[0] != '\0') {
                        upsert_peer(sender_ip_str, declared_port, pid);
                    }
                    
                    /* Répondre avec HELLO_ACK */
                    struct sockaddr_in hello_reply = sender_addr;
                    hello_reply.sin_port = htons((u_short)declared_port);
                    send_hello_ack(socket_net, &hello_reply);
                    
                    /* Ne pas transférer le HELLO au Python (message interne) */
                    continue;
                }

                /* Traitement spécial HELLO_ACK */
                if (strstr(buffer, "\"HELLO_ACK\"")) {
                    /* Intégrer les pairs transmis dans notre table */
                    /* Parsing minimal : cherche "ip":"X","port":Y,"pid":"Z" en boucle */
                    const char *cur = buffer;
                    while ((cur = strstr(cur, "\"ip\":\"")) != NULL) {
                        cur += 6;
                        char peer_ip[64] = "";
                        int pi = 0;
                        while (*cur && *cur != '"' && pi < 63) peer_ip[pi++] = *cur++;
                        peer_ip[pi] = '\0';

                        /* Port */
                        int peer_port = 0;
                        const char *pkey = strstr(cur, "\"port\":");
                        if (pkey) peer_port = atoi(pkey + 7);

                        /* pid */
                        char peer_pid[8] = "?";
                        const char *pidkey = strstr(cur, "\"pid\":\"");
                        if (pidkey) {
                            pidkey += 7;
                            int pk = 0;
                            while (*pidkey && *pidkey != '"' && pk < 7) peer_pid[pk++] = *pidkey++;
                            peer_pid[pk] = '\0';
                        }

                        if (strcmp(peer_ip, "self") != 0 && peer_port > 0) {
                            upsert_peer(peer_ip, peer_port, peer_pid);
                        }
                    }
                    /* Ne pas transférer le HELLO_ACK au Python */
                    continue;
                }

                printf("[NET->IPC] Recu de %s:%d (pid='%s')\n",
                       sender_ip_str, sender_port, pid);

                /* Transfert vers Python local */
                sendto(socket_ipc, buffer, n, 0,
                       (struct sockaddr *)&local_python_addr, sizeof(local_python_addr));
            }
        }
    }

    closesocket(socket_ipc);
    closesocket(socket_net);
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
