#define _DEFAULT_SOURCE

#include <nfc/nfc.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static volatile sig_atomic_t executando = 1;

static void solicitar_encerramento(int sinal) {
    (void)sinal;
    executando = 0;
}

static void imprimir_uid(const nfc_target *alvo) {
    const nfc_iso14443a_info *info = &alvo->nti.nai;

    fputs("UID ", stdout);
    for (size_t indice = 0; indice < info->szUidLen; indice++) {
        printf("%02X", info->abtUid[indice]);
    }
    fputc('\n', stdout);
    fflush(stdout);
}

int main(void) {
    nfc_context *contexto = NULL;
    nfc_device *dispositivo = NULL;
    nfc_target alvo;
    const nfc_modulation modulacao = {
        .nmt = NMT_ISO14443A,
        .nbr = NBR_106,
    };

    signal(SIGINT, solicitar_encerramento);
    signal(SIGTERM, solicitar_encerramento);
    setvbuf(stdout, NULL, _IOLBF, 0);

    nfc_init(&contexto);
    if (contexto == NULL) {
        fputs("Não foi possível inicializar a libnfc.\n", stderr);
        return EXIT_FAILURE;
    }

    dispositivo = nfc_open(contexto, NULL);
    if (dispositivo == NULL) {
        fputs("Não foi possível abrir o PN532.\n", stderr);
        nfc_exit(contexto);
        return EXIT_FAILURE;
    }

    if (nfc_initiator_init(dispositivo) < 0) {
        nfc_perror(dispositivo, "nfc_initiator_init");
        nfc_close(dispositivo);
        nfc_exit(contexto);
        return EXIT_FAILURE;
    }

    printf("READY %s\n", nfc_device_get_name(dispositivo));

    while (executando) {
        /* Um ciclo ISO14443A de aproximadamente 300 ms. */
        int resultado = nfc_initiator_poll_target(
            dispositivo,
            &modulacao,
            1,
            1,
            2,
            &alvo
        );

        if (resultado < 0) {
            if (executando) {
                nfc_perror(dispositivo, "nfc_initiator_poll_target");
            }
            break;
        }

        if (resultado == 0) {
            continue;
        }

        imprimir_uid(&alvo);

        /* Não publica o mesmo cartão novamente enquanto ele continuar presente. */
        while (
            executando &&
            nfc_initiator_target_is_present(dispositivo, NULL) == NFC_SUCCESS
        ) {
            usleep(100000);
        }

        if (executando) {
            nfc_initiator_deselect_target(dispositivo);
        }
    }

    nfc_close(dispositivo);
    nfc_exit(contexto);
    return executando ? EXIT_FAILURE : EXIT_SUCCESS;
}

