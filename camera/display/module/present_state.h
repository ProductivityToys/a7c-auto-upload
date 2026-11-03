#ifndef A7C_PRESENT_STATE_H
#define A7C_PRESENT_STATE_H
#include "event_state.h"
/* First 84 bytes retain the external one-shot controller ABI. */
struct present_marker {
    struct event_marker event;
    unsigned target,pixels,before_ink,after_ink,matched,original_completed;
#ifdef PRESENT_ALIAS_TRIAL
    unsigned alias,alias_before,alias_after,alias_matched;
#endif
#ifdef PRESENT_SYNC_TRIAL
    int sync_rc;
    unsigned sync_created,sync_wait,sync_poll,sync_destroy,sync_elapsed_us;
#endif
};
#endif
