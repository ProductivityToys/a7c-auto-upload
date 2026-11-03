/* Included after the font adapter's fd declaration. Only four DDS RAM bytes.
 * Coordinates are immutable in both fork copies before the first write.
 * Uses the native screen viewport; does not change bitmap dimensions or code.
 */
static const unsigned char original_position[4]={30,0,250,0};
static const unsigned char edge_position[4]={24,2,176,1}; /* (536,432) */
/* Keep the full clipped DDS background clear of native ISO 1600, not only ink. */
static const unsigned char shooting_position[4]={SHOOTING_X&255,SHOOTING_X>>8,
 SHOOTING_Y&255,SHOOTING_Y>>8}; /* (562,432), small24 ink fits within 640 */
static const unsigned char *position_target(void){
 return shooting_overlay_mode?shooting_position:edge_position;
}
static int position_read(unsigned char *out){
 struct native_state s;
 if(snapshot(&s)||s.life[3]!=timer_id)return -1;
 memcpy(out,s.slots+200,4);return 0;
}
static int position_check(void){
 unsigned char now[4];
 return position_read(now)||memcmp(now,original_position,4)?95:0;
}
static int position_change(int restore){
 unsigned char now[4];
 const unsigned char *candidate=position_target();
 const unsigned char *target=restore?original_position:candidate;
 if(position_read(now))return 95;
 if(restore){
  if(!memcmp(now,original_position,4))return 0;
  for(unsigned i=0;i<4;i++)
   if(now[i]!=original_position[i]&&now[i]!=candidate[i])return 95;
 }else if(memcmp(now,original_position,4))return 95;
 unsigned off=0;
 while(off<4){
  struct native_state s;
  if(snapshot(&s)||s.life[3]!=timer_id)return 95;
  int n=pwrite(font_fd,target+off,4-off,(long)(base+STATE+200+off));
  if(n<=0||(unsigned)n>4-off)return 95;
  off+=(unsigned)n;
 }
 if(position_read(now)||memcmp(now,target,4))return 95;
 return 0;
}
