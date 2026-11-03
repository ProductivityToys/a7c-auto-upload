#include "../../uploader/compat.h"
#include "../module/rpc_guard.h"
#include <assert.h>

static int sequence(const char *commands){
 int p[2];assert(!pipe(p));
 assert(write(p[1],commands,strlen(commands))==(int)strlen(commands));close(p[1]);
 int result=module_guard_wait(p[0],150);close(p[0]);return result;
}
static void sender_dies_with_request_in_flight(void){
 int p[2],ready[2];assert(!pipe(p)&&!pipe(ready));int sender=fork();assert(sender>=0);
 if(!sender){
  close(p[0]);close(ready[0]);assert(write(p[1],"B",1)==1);
  assert(write(ready[1],"1",1)==1);for(;;)pause();
 }
 close(p[1]);close(ready[1]);char c;assert(read(ready[0],&c,1)==1);close(ready[0]);
 assert(!kill(sender,SIGKILL));int status;assert(waitpid(sender,&status,0)==sender);
 assert(module_guard_wait(p[0],150)==MODULE_GUARD_UNKNOWN);close(p[0]);
 assert(!module_rpc_complete(sender,sender,status,8,0));
}
static void request_stays_in_flight(void){
 int p[2];assert(!pipe(p));assert(write(p[1],"B",1)==1);
 unsigned begin=millis();assert(module_guard_wait(p[0],100)==MODULE_GUARD_UNKNOWN);
 assert(millis()-begin>=90);close(p[0]);close(p[1]);
}
int main(void){
 assert(sequence("")==MODULE_GUARD_CLEANUP);
 assert(sequence("BKD")==MODULE_GUARD_COMMITTED);
 assert(sequence("BKCBK")==MODULE_GUARD_CLEANUP);
 assert(sequence("B")==MODULE_GUARD_UNKNOWN);
 assert(sequence("BKCB")==MODULE_GUARD_UNKNOWN); /* unload reply lost */
 assert(sequence("BD")==MODULE_GUARD_UNKNOWN); /* false commit */
 assert(sequence("BB")==MODULE_GUARD_UNKNOWN);
 assert(sequence("K")==MODULE_GUARD_UNKNOWN);
 assert(sequence("X")==MODULE_GUARD_UNKNOWN);
 assert(module_rpc_complete(123,123,0,8,0));
 assert(!module_rpc_complete(-1,123,0,8,0));
 assert(!module_rpc_complete(123,123,0,4,0));
 assert(!module_rpc_complete(123,123,0,8,-1));
 sender_dies_with_request_in_flight();request_stays_in_flight();
 puts("PASS module RPC guardian: killed sender, lost load/unload reply, timeout, malformed commit, confirmed cleanup");
 return 0;
}
