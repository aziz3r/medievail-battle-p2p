/*
 * reseau.c — Routeur UDP P2P (Windows / Winsock2)
 *
 * Fait le pont entre le jeu Python local et l'adversaire distant
 * en ecoutant simultanement deux sockets UDP via select().
 *
 * Flux sortant : Python (PORT_IPC_IN) --> C --> Adversaire (REMOTE_IP:REMOTE_PORT)
 * Flux entrant : Adversaire (PORT_NET_IN) --> C --> Python (127.0.0.1:PORT_IPC_OUT)
 *
 * Compilation : gcc reseau.c -o reseau.exe -lws2_32
 * Lancement   : reseau.exe
 */

#include <stdio.h>
#include <string.h>
#include <winsock2.h>

/* --- Configuration ------------------------------------------------------- */
#define PORT_IPC_IN   5000          /* Le C ecoute le Python local ici        */
#define PORT_IPC_OUT  5001          /* Le C renvoie vers le Python local ici  */
#define PORT_NET_IN   6000          /* Le C ecoute l'adversaire ici           */
#define REMOTE_IP     "127.0.0.1"   /* IP de l'adversaire (localhost = tests) */
#define REMOTE_PORT   6001          /* Port d'ecoute de l'adversaire          */

#define BUFFER_SIZE   4096
#define ACK_MSG       "[C-Routeur] OK - message transmis au reseau."
/* ------------------------------------------------------------------------- */

/* Cree, configure et bind un socket UDP sur l'adresse et le port donnes.
   Retourne INVALID_SOCKET en cas d'echec. */
static SOCKET create_udp_socket(const char *bind_ip, int port)
{
    SOCKET sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock == INVALID_SOCKET) {
        fprintf(stderr, "[ERREUR] socket() : %d\n", WSAGetLastError());
        return INVALID_SOCKET;
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons((u_short)port);
    addr.sin_addr.s_addr = inet_addr(bind_ip);

    if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) == SOCKET_ERROR) {
        fprintf(stderr, "[ERREUR] bind() sur port %d : %d\n", port, WSAGetLastError());
        closesocket(sock);
        return INVALID_SOCKET;
    }
    return sock;
}

int main(void)
{
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        fprintf(stderr, "[ERREUR] WSAStartup : %d\n", WSAGetLastError());
        return 1;
    }

    /* -- Initialisation des sockets --------------------------------------- */
    SOCKET socket_ipc = create_udp_socket("127.0.0.1", PORT_IPC_IN);
    SOCKET socket_net = create_udp_socket("0.0.0.0",   PORT_NET_IN);

    if (socket_ipc == INVALID_SOCKET || socket_net == INVALID_SOCKET) {
        WSACleanup();
        return 1;
    }

    printf("==================================================\n");
    printf("       ROUTEUR UDP P2P - demarre                 \n");
    printf("==================================================\n");
    printf("  [IPC] Ecoute Python local  -> port %d\n", PORT_IPC_IN);
    printf("  [IPC] Renvoie vers Python  -> port %d\n", PORT_IPC_OUT);
    printf("  [NET] Ecoute adversaire    -> port %d\n", PORT_NET_IN);
    printf("  [NET] Envoie vers          -> %s:%d\n", REMOTE_IP, REMOTE_PORT);
    printf("==================================================\n\n");

    /* -- Adresses de destination pre-construites -------------------------- */

    /* Vers l'adversaire distant (via socket_net) */
    struct sockaddr_in remote_addr;
    memset(&remote_addr, 0, sizeof(remote_addr));
    remote_addr.sin_family      = AF_INET;
    remote_addr.sin_port        = htons(REMOTE_PORT);
    remote_addr.sin_addr.s_addr = inet_addr(REMOTE_IP);

    /* Vers le Python local sur PORT_IPC_OUT (via socket_ipc) */
    struct sockaddr_in local_python_addr;
    memset(&local_python_addr, 0, sizeof(local_python_addr));
    local_python_addr.sin_family      = AF_INET;
    local_python_addr.sin_port        = htons(PORT_IPC_OUT);
    local_python_addr.sin_addr.s_addr = inet_addr("127.0.0.1");

    /* -- Boucle principale avec select() ---------------------------------- */
    char buffer[BUFFER_SIZE];
    struct sockaddr_in sender_addr;
    int sender_len;

    while (1) {
        /* Prepare le fd_set a chaque iteration (select() le modifie) */
        fd_set read_fds;
        FD_ZERO(&read_fds);
        FD_SET(socket_ipc, &read_fds);
        FD_SET(socket_net, &read_fds);

        /* Attend indefiniment qu'un socket soit pret (timeout = NULL) */
        int ready = select(0, &read_fds, NULL, NULL, NULL);
        if (ready == SOCKET_ERROR) {
            fprintf(stderr, "[ERREUR] select() : %d\n", WSAGetLastError());
            break;
        }

        /* == Flux SORTANT : Python local --> Adversaire distant =========== */
        if (FD_ISSET(socket_ipc, &read_fds)) {
            memset(buffer, 0, BUFFER_SIZE);
            sender_len = sizeof(sender_addr);

            int n = recvfrom(socket_ipc, buffer, BUFFER_SIZE - 1, 0,
                             (struct sockaddr *)&sender_addr, &sender_len);
            if (n > 0) {
                printf("[>>] [IPC->NET] Recu du Python (%d octets) : %s\n", n, buffer);

                /* FIX: on envoie via socket_NET (pas socket_ipc) vers l'adversaire */
                int sent = sendto(socket_net, buffer, n, 0,
                                  (struct sockaddr *)&remote_addr, sizeof(remote_addr));
                if (sent == SOCKET_ERROR)
                    fprintf(stderr, "     [ERREUR] sendto adversaire : %d\n", WSAGetLastError());
                else
                    printf("     [>>] Transmis a %s:%d\n\n", REMOTE_IP, REMOTE_PORT);

                /* ACK vers Python pour eviter son timeout */
                sendto(socket_ipc, ACK_MSG, (int)strlen(ACK_MSG), 0,
                       (struct sockaddr *)&sender_addr, sender_len);
            }
        }

        /* == Flux ENTRANT : Adversaire distant --> Python local ============ */
        if (FD_ISSET(socket_net, &read_fds)) {
            memset(buffer, 0, BUFFER_SIZE);
            sender_len = sizeof(sender_addr);

            int n = recvfrom(socket_net, buffer, BUFFER_SIZE - 1, 0,
                             (struct sockaddr *)&sender_addr, &sender_len);
            if (n > 0) {
                printf("[<<] [NET->IPC] Recu de l'adversaire (%d octets) : %s\n", n, buffer);

                /* FIX: on envoie via socket_IPC (pas socket_net) vers le Python local */
                int sent = sendto(socket_ipc, buffer, n, 0,
                                  (struct sockaddr *)&local_python_addr, sizeof(local_python_addr));
                if (sent == SOCKET_ERROR)
                    fprintf(stderr, "     [ERREUR] sendto Python local : %d\n", WSAGetLastError());
                else
                    printf("     [<<] Transmis au Python local sur port %d\n\n", PORT_IPC_OUT);
            }
        }
    }

    /* -- Nettoyage --------------------------------------------------------- */
    closesocket(socket_ipc);
    closesocket(socket_net);
    WSACleanup();
    return 0;
}
