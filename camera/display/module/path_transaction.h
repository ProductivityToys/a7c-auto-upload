/* Exactly one pinned 15-byte pathname; I/O adapters enforce target identity. */
#define PATH_BYTES 15
struct path_transaction {
    unsigned char original[PATH_BYTES],replacement[PATH_BYTES];
    int (*read)(unsigned char *);
    int (*write)(unsigned,const unsigned char *,unsigned);
};
static int path_equal(const unsigned char *a,const unsigned char *b) {
    for(unsigned i=0;i<PATH_BYTES;i++)if(a[i]!=b[i])return 0;return 1;
}
static int path_write(struct path_transaction *t,const unsigned char *bytes) {
    for(unsigned off=0;off<PATH_BYTES;) {
        int n=t->write(off,bytes+off,PATH_BYTES-off);
        if(n<=0 || (unsigned)n>PATH_BYTES-off)return 3;off+=(unsigned)n;
    }
    unsigned char now[PATH_BYTES];
    return t->read(now)?1:path_equal(now,bytes)?0:4;
}
static int path_install(struct path_transaction *t) {
    unsigned char now[PATH_BYTES];
    if(t->read(now))return 1;if(!path_equal(now,t->original))return 2;
    return path_write(t,t->replacement);
}
static int path_restore(struct path_transaction *t) {
    unsigned char now[PATH_BYTES];
    if(t->read(now))return 1;if(path_equal(now,t->original))return 0;
    for(unsigned i=0;i<PATH_BYTES;i++)
        if(now[i]!=t->original[i] && now[i]!=t->replacement[i])return 2;
    return path_write(t,t->original);
}
