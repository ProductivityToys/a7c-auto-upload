/* Aligned data-pointer handoff only; no ARM instruction or trampoline writes.
 * Single installer; immutable originals and wrapper code survive retirement.
 * Saved slot may be the native lazy resolver, while original is the verified
 * callable function body. Never call the resolver as an ordinary C function.
 * Restore the saved slot or accept normal loader resolution; keep foreign values.
 * Wrappers MUST always forward once, including partial install and late calls.
 * This pair is for observation only: it is not an atomic two-hook drawing
 * transaction. A renderer needs an explicit in-flight-frame contract. */
struct dds_import_handoff {
    unsigned *slot[2],saved[2],original[2],self[2],prepared,enabled;
};
static int dds_import_prepare(struct dds_import_handoff *h,unsigned *a,unsigned *b,
        unsigned va,unsigned vb,unsigned oa,unsigned ob,unsigned sa,unsigned sb) {
    if(h->prepared||!a||!b||a==b||((unsigned long)a&3)||((unsigned long)b&3)||
       !va||!vb||!oa||!ob||!sa||!sb||oa==sa||ob==sb||va==sa||vb==sb)return -1;
    h->slot[0]=a;h->slot[1]=b;h->saved[0]=va;h->saved[1]=vb;h->original[0]=oa;h->original[1]=ob;
    h->self[0]=sa;h->self[1]=sb;h->prepared=1;h->enabled=0;
    return 0;
}
static unsigned dds_import_restore(struct dds_import_handoff *h) {
    if(!h->prepared)return 4;
    __atomic_store_n(&h->enabled,0,__ATOMIC_RELEASE);
    unsigned conflicts=0;
    for(unsigned i=0;i<2;i++) {
        unsigned expected=h->self[i];
        if(!__atomic_compare_exchange_n(h->slot[i],&expected,h->saved[i],0,
                    __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)&&expected!=h->saved[i]&&expected!=h->original[i])
            conflicts|=1U<<i;
    }
    return conflicts;
}
static int dds_import_install(struct dds_import_handoff *h) {
    if(!h->prepared||__atomic_load_n(&h->enabled,__ATOMIC_ACQUIRE))return -1;
    for(unsigned i=0;i<2;i++) {
        unsigned expected=h->saved[i];
        if(!__atomic_compare_exchange_n(h->slot[i],&expected,h->self[i],0,
                                        __ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) {
            dds_import_restore(h);return -2;
        }
    }
    __atomic_store_n(&h->enabled,1,__ATOMIC_RELEASE);return 0;
}
