/* Experimental SD receipt codec. No filesystem, network or camera operations. */
#ifndef A7C_RECEIPT_H
#define A7C_RECEIPT_H

#define A7C_RECEIPT_BYTES 512
typedef unsigned long long ReceiptSize;
typedef struct {
    ReceiptSize bytes;
    unsigned char destination[32];
    unsigned char identity[32];
    /* Zero when FTP_SIZE was established without hashing the video body.
     * REMOTE_SHA256 always requires a real nonzero content digest. */
    unsigned char source_sha256[32];
    unsigned char remote_path[32];
    /* Evidence supplied by the caller, never established by this codec. */
    unsigned proof;
} A7cReceipt;
enum { A7C_PROOF_FTP_SIZE = 1, A7C_PROOF_REMOTE_SHA256 = 2 };
enum { A7C_RECORD_OK, A7C_RECORD_INVALID, A7C_RECORD_UNSUPPORTED };
enum { A7C_SLOT_ABSENT, A7C_SLOT_READ, A7C_SLOT_UNKNOWN };
typedef struct {
    const unsigned char *data;
    unsigned length;
    unsigned state;
} A7cReceiptSlot;
enum {
    A7C_RECEIPT_RETRY,       /* Neither slot proves completion. */
    A7C_RECEIPT_SKIP,        /* Matching local receipt, not remote existence check. */
    A7C_RECEIPT_HOLD,        /* Unreadable/foreign/unsupported: do not overwrite. */
    A7C_RECEIPT_CONFLICT,    /* Same identity, different source content. */
    A7C_RECEIPT_NEED_PROOF  /* Receipt weaker than configured verification policy. */
};
int a7c_receipt_encode(const A7cReceipt *r, unsigned char out[A7C_RECEIPT_BYTES]);
int a7c_receipt_decode(const unsigned char *data, unsigned length, A7cReceipt *out);
/* expected.source_sha256/proof are ignored: the current source has not been
 * streamed yet. The caller must derive identity from fresh stable metadata.
 * selected is -1 unless SKIP. No write/repair is performed by this function. */
int a7c_receipt_recover(const A7cReceiptSlot slots[2], const A7cReceipt *expected,
                        unsigned minimum_proof, int *selected);
#endif
