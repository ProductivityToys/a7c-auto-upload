/* Fixed read-only identity request, ILCE-7C 2.00 only. No command arguments,
 * module loading or memory writes. Host verifies im/libosal hashes first. */
extern int osal_snd_sync_direct(unsigned,void *);
extern int printf(const char *,...);
extern unsigned alarm(unsigned);
int main(void) {
    unsigned message[8]={32,0,0,0,0x9400e1,0,0,0};
    alarm(5);
    int rc=osal_snd_sync_direct(0x94016a,message);
    printf("IM_IDENTITY transport=%d bytes=%u op=%08x magic=%08x state=%08x\n",
           rc,message[0],message[4],message[5],message[6]);
    return rc?65:message[5]!=0x12345678?66:0;
}
