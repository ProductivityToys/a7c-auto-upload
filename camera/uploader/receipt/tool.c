/* Experimental pure codec CLI. Binary stdout only; caller stages it in RAM.
 * Does not assert upload completion, access SD, or change the uploader. */
#include "receipt.h"
extern int read(int, void *, unsigned), write(int, const void *, unsigned);
extern int strcmp(const char *, const char *);
static int hex32(const char *s, unsigned char out[32]) {
    for (unsigned i = 0; i < 64; i++) {
        unsigned c = (unsigned char)s[i], v;
        if (c >= '0' && c <= '9') v = c-'0';
        else if (c >= 'a' && c <= 'f') v = c-'a'+10;
        else return 0;
        if (!(i & 1)) out[i/2] = v << 4; else out[i/2] |= v;
    }
    return s[64] == 0;
}
static int size64(const char *s, ReceiptSize *v) {
    *v = 0;
    if (!*s || *s == '0') return 0;
    for (; *s; s++) {
        /* Constant boundary avoids the ARM compiler-runtime 64-bit division
         * helper, which is unavailable in the camera's minimal ABI link. */
        if (*s < '0' || *s > '9' || *v > 1844674407370955161ULL
            || (*v == 1844674407370955161ULL && *s > '5')) return 0;
        *v = *v*10 + (*s-'0');
    }
    return 1;
}
int main(int argc, char **argv) {
    A7cReceipt r = {0}; unsigned char record[513];
    /* encode destination identity size source_sha256 remote_path proof */
    if (argc == 8 && !strcmp(argv[1], "encode")) {
        if (!hex32(argv[2], r.destination) || !hex32(argv[3], r.identity)
            || !size64(argv[4], &r.bytes) || !hex32(argv[5], r.source_sha256)
            || !hex32(argv[6], r.remote_path)) return 64;
        if (!strcmp(argv[7], "ftp-size")) r.proof = A7C_PROOF_FTP_SIZE;
        else if (!strcmp(argv[7], "remote-sha256")) r.proof = A7C_PROOF_REMOTE_SHA256;
        else return 64;
        if (a7c_receipt_encode(&r, record)) return 65;
        for (unsigned n = 0; n < 512;) {
            int w = write(1, record+n, 512-n);
            if (w <= 0) return 74;
            n += (unsigned)w;
        }
        return 0;
    }
    /* verify destination identity size remote_path minimum_proof; one record on stdin */
    if (argc == 7 && !strcmp(argv[1], "verify")) {
        if (!hex32(argv[2], r.destination) || !hex32(argv[3], r.identity)
            || !size64(argv[4], &r.bytes) || !hex32(argv[5], r.remote_path)) return 64;
        unsigned minimum = !strcmp(argv[6], "remote-sha256") ? 2 :
            (!strcmp(argv[6], "ftp-size") ? 1 : 0);
        if (!minimum) return 64;
        unsigned n = 0;
        while (n < sizeof(record)) {
            int count = read(0, record+n, sizeof(record)-n);
            if (count < 0) return 74;
            if (!count) break;
            n += (unsigned)count;
        }
        A7cReceiptSlot slots[2] = {{record, n, A7C_SLOT_READ}, {0, 0, A7C_SLOT_ABSENT}};
        int selected;
        int result = a7c_receipt_recover(slots, &r, minimum, &selected);
        return result == A7C_RECEIPT_SKIP ? 0 : 10+result;
    }
    return 64;
}
