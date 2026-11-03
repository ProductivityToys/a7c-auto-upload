/* Service-trial guardian: a sender timeout does not cancel an IM request.
 * B precedes dispatch, K follows a complete transport reply. Never submit a
 * second native operation while the first one's outcome is unknown.
 * Uses the existing guardian pipe; no camera thread or persistent state.
 */
#ifndef A7C_MODULE_RPC_GUARD_H
#define A7C_MODULE_RPC_GUARD_H
enum { MODULE_GUARD_CLEANUP=0, MODULE_GUARD_COMMITTED=1, MODULE_GUARD_UNKNOWN=2 };
static int module_rpc_complete(int waited,int child,int status,int bytes,int transport){
 return waited==child && status==0 && bytes==2*(int)sizeof(int) && transport==0;
}
static int module_guard_wait(int fd,unsigned timeout_ms){
 struct pollfd p={fd,1,0};unsigned began=millis();int pending=0;
 for(;;){
  unsigned elapsed=millis()-began;
  if(elapsed>=timeout_ms)return pending?MODULE_GUARD_UNKNOWN:MODULE_GUARD_CLEANUP;
  if(poll(&p,1,(int)(timeout_ms-elapsed))<=0)
   return pending?MODULE_GUARD_UNKNOWN:MODULE_GUARD_CLEANUP;
  char c=0;if(read(fd,&c,1)!=1)
   return pending?MODULE_GUARD_UNKNOWN:MODULE_GUARD_CLEANUP;
  if(c=='B'&&!pending){pending=1;continue;}
  if(c=='K'&&pending){pending=0;continue;}
  if(c=='D'&&!pending)return MODULE_GUARD_COMMITTED;
  if((c=='C'||c=='H')&&!pending)continue;
  return MODULE_GUARD_UNKNOWN;
 }
}
#endif
