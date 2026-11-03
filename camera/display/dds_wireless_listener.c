/* Authenticated, bounded one-shot display transport; no power lease commands. */
#define DISPLAY_OBSERVER_ONLY
#define DISPLAY_TRANSFER_PROTOCOL
#define DISPLAY_BLINK_CONTROL
#define ROOT "/setting/a7c-debug/ram/dds-once"
#define RAM ROOT
#define PORT 21217
/* Four sequential guarded displays; ordinary debugger keeps its 20 s bound. */
#define ACTION_TIMEOUT_MS 60000
#include "../debugger/listener.c"
