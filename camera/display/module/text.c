/* Research only: original TextRM -> module-owned RAM, never a display surface.
 * im has initialized libObj already. Do not call init or change font registry.
 * Each successful native object/reference is released before init returns. */
#include "text_state.h"
extern int TextRM_loadFont(const char *,U *),TextRM_unloadFont(U);
extern int TextRM_createText(const char *,U,U,void *,short,U *);
extern int TextRM_getBounds(U,void *),TextRM_drawText(U,void *,void *,U *);
extern int TextRM_deleteText(U);
#define API __attribute__((visibility("default")))
#ifdef MANAGED_TRIAL
struct dimensions {H width,height;U stride;};
#define A7C_MANAGED_IMPLEMENTATION
#include "managed_buffer.h"
API struct managed_state a7c_native_marker={.text={.magic=0x41374d31U,
#ifdef SMALL_POOL_TRIAL
    .version=6
#elif defined(SHARED_POOL_TRIAL)
    .version=5
#elif defined(COMPOSE_TRIAL)
    .version=4
#else
    .version=3
#endif
}};
#define STATE a7c_native_marker.text
#else
API struct text_state a7c_native_marker={.magic=0x41374d31U,.version=2};
struct dimensions {H width,height;U stride;};
#define STATE a7c_native_marker
#endif
API int IM_SAMPLE_SO_init(void) {
    struct text_state *s=&STATE;
    s->init++;
    if(s->init!=1)return -1; /* immutable, one execution only */
    U font=0,text=0,changed=0;
    s->phase=1;
    s->load_rc=TextRM_loadFont("FONT_UNIVERS",&font);
    if(s->load_rc)return -2;
    U attributes[12];
    for(U i=0;i<12;i++)((volatile U *)attributes)[i]=0;
    attributes[0]=font;attributes[1]=1;attributes[2]=(20U<<16)|20U;
    attributes[3]=1;attributes[4]=0xffffffff;
    s->phase=2;
    s->create_rc=TextRM_createText("UD 42%",0,0x8ff,attributes,0,&text);
    if(!s->create_rc) {
        struct dimensions d={0};
        s->phase=3;s->bounds_rc=TextRM_getBounds(text,&d);
        s->width=d.width;s->height=d.height;s->stride=d.stride;
        if(!s->bounds_rc && d.width && d.width<=128 && d.height==20 &&
           d.stride==2U*d.width && d.stride*d.height<=TEXT_BYTES) {
            s->bytes=d.stride*d.height;
            for(U i=0;i<TEXT_GUARD;i++)
                s->storage[i]=s->storage[TEXT_GUARD+s->bytes+i]=0x5a;
            unsigned char *pixels=s->storage+TEXT_GUARD;
            s->phase=4;
#ifdef MANAGED_TRIAL
            s->draw_rc=managed_draw(&a7c_native_marker,(U)&TextRM_loadFont-0x57d271,text,&d,&changed);
#else
            s->draw_rc=TextRM_drawText(text,&d,pixels,&changed);
#endif
            s->guard_ok=1;
            for(U i=0;i<TEXT_GUARD;i++)
                if(s->storage[i]!=0x5a || pixels[s->bytes+i]!=0x5a)s->guard_ok=0;
            for(U i=0;i<s->bytes;i+=2) {
                U v=pixels[i]|((U)pixels[i+1]<<8),alpha=v&15;
                if(v)s->ink++;else s->transparent++;
                if(alpha && alpha<15)s->aa++;
            }
        } else s->bounds_rc=s->bounds_rc?s->bounds_rc:-100;
        s->phase=5;s->delete_rc=TextRM_deleteText(text);
    }
    s->phase=6;s->unload_rc=TextRM_unloadFont(font);
    s->phase=7;
    return s->create_rc||s->bounds_rc||s->draw_rc||s->delete_rc||s->unload_rc||
           !s->guard_ok||!s->ink||!s->aa||!s->transparent?-3:0;
}
API int IM_SAMPLE_SO_exit(void){STATE.exit++;return 0;}
API int IM_SAMPLE_SO_sus(void){STATE.suspend++;return 0;}
API int IM_SAMPLE_SO_res(void){STATE.resume++;return 0;}
API int IM_SAMPLE_SO_inact(void){STATE.inactive++;return 0;}
API int IM_SAMPLE_SO_act(void){STATE.active++;return 0;}
