#include "receipt.h"
typedef unsigned int u32;
typedef unsigned long long u64;
#include "../sha256.h"

static const unsigned char magic[8] = {'A','7','C','R','C','P','\r','\n'};
static void copy_bytes(unsigned char *d, const unsigned char *s, unsigned n) {
    for (unsigned i = 0; i < n; i++) d[i] = s[i];
}
static int equal(const unsigned char *a, const unsigned char *b, unsigned n) {
    for (unsigned i = 0; i < n; i++) if (a[i] != b[i]) return 0;
    return 1;
}
static int nonzero(const unsigned char *a) {
    unsigned v = 0;
    for (unsigned i = 0; i < 32; i++) v |= a[i];
    return v != 0;
}
static int valid_key(const A7cReceipt *r) {
    return r && r->bytes && nonzero(r->destination) && nonzero(r->identity)
        && nonzero(r->remote_path);
}
static unsigned unhex(char c) { return c <= '9' ? c - '0' : c - 'a' + 10; }
static void checksum(const unsigned char *data, unsigned char out[32]) {
    Sha sha; char hex[65];
    sha_init(&sha); sha_update(&sha, data, 480); sha_final(&sha, hex);
    for (unsigned i = 0; i < 32; i++) out[i] = (unhex(hex[2*i]) << 4) | unhex(hex[2*i+1]);
}
int a7c_receipt_encode(const A7cReceipt *r, unsigned char out[512]) {
    if (!out || !valid_key(r)
        || (r->proof == A7C_PROOF_REMOTE_SHA256 && !nonzero(r->source_sha256))
        || (r->proof != A7C_PROOF_FTP_SIZE && r->proof != A7C_PROOF_REMOTE_SHA256))
        return A7C_RECORD_INVALID;
    for (unsigned i = 0; i < 512; i++) out[i] = 0;
    copy_bytes(out, magic, 8);
    out[8] = 1; out[9] = r->proof; out[10] = 0; out[11] = 2;
    for (unsigned i = 0; i < 8; i++) out[16+i] = r->bytes >> (i*8);
    copy_bytes(out+24, r->destination, 32);
    copy_bytes(out+56, r->identity, 32);
    copy_bytes(out+88, r->source_sha256, 32);
    copy_bytes(out+120, r->remote_path, 32);
    checksum(out, out+480);
    return A7C_RECORD_OK;
}
int a7c_receipt_decode(const unsigned char *data, unsigned length, A7cReceipt *out) {
    unsigned char digest[32]; A7cReceipt r = {0};
    if (!data || !out || length != 512) return A7C_RECORD_INVALID;
    checksum(data, digest);
    if (!equal(digest, data+480, 32) || !equal(data, magic, 8)) return A7C_RECORD_INVALID;
    if (data[8] != 1) return A7C_RECORD_UNSUPPORTED;
    if (data[10] || data[11] != 2) return A7C_RECORD_INVALID;
    if (data[9] != A7C_PROOF_FTP_SIZE && data[9] != A7C_PROOF_REMOTE_SHA256)
        return A7C_RECORD_UNSUPPORTED;
    for (unsigned i = 12; i < 16; i++) if (data[i]) return A7C_RECORD_INVALID;
    for (unsigned i = 152; i < 480; i++) if (data[i]) return A7C_RECORD_INVALID;
    for (unsigned i = 0; i < 8; i++) r.bytes |= (u64)data[16+i] << (i*8);
    r.proof = data[9];
    copy_bytes(r.destination, data+24, 32);
    copy_bytes(r.identity, data+56, 32);
    copy_bytes(r.source_sha256, data+88, 32);
    copy_bytes(r.remote_path, data+120, 32);
    if (!valid_key(&r) || (r.proof == A7C_PROOF_REMOTE_SHA256 && !nonzero(r.source_sha256)))
        return A7C_RECORD_INVALID;
    *out = r;
    return A7C_RECORD_OK;
}
static int matches(const A7cReceipt *a, const A7cReceipt *b) {
    return a->bytes == b->bytes && equal(a->destination, b->destination, 32)
        && equal(a->identity, b->identity, 32) && equal(a->remote_path, b->remote_path, 32);
}
int a7c_receipt_recover(const A7cReceiptSlot slots[2], const A7cReceipt *expected,
                        unsigned minimum_proof, int *selected) {
    A7cReceipt r[2]; int valid[2] = {0, 0};
    if (!selected) return A7C_RECEIPT_HOLD;
    *selected = -1;
    if (!slots || !valid_key(expected) || (minimum_proof != A7C_PROOF_FTP_SIZE
        && minimum_proof != A7C_PROOF_REMOTE_SHA256)) return A7C_RECEIPT_HOLD;
    for (unsigned i = 0; i < 2; i++) {
        if (slots[i].state == A7C_SLOT_ABSENT) continue;
        if (slots[i].state != A7C_SLOT_READ) return A7C_RECEIPT_HOLD;
        int rc = a7c_receipt_decode(slots[i].data, slots[i].length, &r[i]);
        if (rc == A7C_RECORD_UNSUPPORTED) return A7C_RECEIPT_HOLD;
        if (rc != A7C_RECORD_OK) continue;
        if (!matches(&r[i], expected)) return A7C_RECEIPT_HOLD;
        valid[i] = 1;
    }
    if (valid[0] && valid[1] && nonzero(r[0].source_sha256) && nonzero(r[1].source_sha256)
        && !equal(r[0].source_sha256, r[1].source_sha256, 32))
        return A7C_RECEIPT_CONFLICT;
    int best = valid[0] ? 0 : (valid[1] ? 1 : -1);
    if (best < 0) return A7C_RECEIPT_RETRY;
    if (valid[1] && r[1].proof > r[best].proof) best = 1;
    if (r[best].proof < minimum_proof) return A7C_RECEIPT_NEED_PROOF;
    *selected = best;
    return A7C_RECEIPT_SKIP;
}
