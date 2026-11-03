#ifndef A7C_EVENT_STATE_H
#define A7C_EVENT_STATE_H
/* Fixed ARM32 marker ABI shared by module and external read-only inspector. */
struct event_marker {
    unsigned magic,version,init,exit,suspend,resume,inactive,active;
    int prepare_rc,restore_rc,capture_rc;
    unsigned captured,tid,sec,nsec,slot,original,init_tid,exit_tid,view,internal;
};
#endif
