/* Owned RAM output, readable after native exit. No camera/UI pointers exported. */
#ifndef A7C_TEXT_STATE_H
#define A7C_TEXT_STATE_H
typedef unsigned U;
typedef unsigned short H;
#define TEXT_BYTES 4096U
#define TEXT_GUARD 64U
struct text_state {
    U magic,version,init,exit,suspend,resume,inactive,active;
    U phase;
    int load_rc,create_rc,bounds_rc,draw_rc,delete_rc,unload_rc;
    U width,height,stride,bytes,guard_ok,ink,aa,transparent;
    unsigned char storage[TEXT_BYTES+2*TEXT_GUARD];
};
#endif
