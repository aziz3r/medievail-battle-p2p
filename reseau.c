#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

#define SERVER_IP "127.0.0.1"
#define SERVER_PORT 5000
#define BUFFER_SIZE 1024

#ifdef _WIN32
#define CLOSE_SOCKET closesocket
#else
#define CLOSE_SOCKET close
typedef int SOCKET;
#define INVALID_SOCKET (-1)
#define SOCKET_ERROR (-1)
#endif

static void print_socket_error(const char *context) {
#ifdef _WIN32
    fprintf(stderr, "%s: erreur Winsock %d\n", context, WSAGetLastError());
#else
    perror(context);
#endif
}

int main(void) {
#ifdef _WIN32
    WSADATA wsa_data;
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
        fprintf(stderr, "WSAStartup a echoue.\n");
        return EXIT_FAILURE;
    }
#endif

    SOCKET server_fd;
    struct sockaddr_in server_addr;

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd == INVALID_SOCKET) {
        print_socket_error("socket");
#ifdef _WIN32
        WSACleanup();
#endif
        return EXIT_FAILURE;
    }

    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, (const char *)&opt, sizeof(opt)) ==
        SOCKET_ERROR) {
        print_socket_error("setsockopt");
        CLOSE_SOCKET(server_fd);
#ifdef _WIN32
        WSACleanup();
#endif
        return EXIT_FAILURE;
    }

    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(SERVER_PORT);

    if (inet_pton(AF_INET, SERVER_IP, &server_addr.sin_addr) <= 0) {
        print_socket_error("inet_pton");
        CLOSE_SOCKET(server_fd);
#ifdef _WIN32
        WSACleanup();
#endif
        return EXIT_FAILURE;
    }

    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) == SOCKET_ERROR) {
        print_socket_error("bind");
        CLOSE_SOCKET(server_fd);
#ifdef _WIN32
        WSACleanup();
#endif
        return EXIT_FAILURE;
    }

    if (listen(server_fd, 5) == SOCKET_ERROR) {
        print_socket_error("listen");
        CLOSE_SOCKET(server_fd);
#ifdef _WIN32
        WSACleanup();
#endif
        return EXIT_FAILURE;
    }

    printf("Serveur C en ecoute sur %s:%d...\n", SERVER_IP, SERVER_PORT);

    while (1) {
        SOCKET client_fd;
        char buffer[BUFFER_SIZE];
        int bytes_read;
        const char *reply = "Bien recu";

        client_fd = accept(server_fd, NULL, NULL);
        if (client_fd == INVALID_SOCKET) {
            print_socket_error("accept");
            continue;
        }

        bytes_read = recv(client_fd, buffer, BUFFER_SIZE - 1, 0);
        if (bytes_read == SOCKET_ERROR) {
            print_socket_error("recv");
            CLOSE_SOCKET(client_fd);
            continue;
        }

        if (bytes_read == 0) {
            printf("Client connecte puis deconnecte sans envoyer de donnees.\n");
            CLOSE_SOCKET(client_fd);
            continue;
        }

        buffer[bytes_read] = '\0';
        printf("Message recu: %s\n", buffer);

        if (send(client_fd, reply, (int)strlen(reply), 0) == SOCKET_ERROR) {
            print_socket_error("send");
        }

        CLOSE_SOCKET(client_fd);
    }

    CLOSE_SOCKET(server_fd);
#ifdef _WIN32
    WSACleanup();
#endif
    return EXIT_SUCCESS;
}
