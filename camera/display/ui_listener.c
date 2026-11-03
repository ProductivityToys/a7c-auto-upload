/* Private RAM instance of the existing authenticated transport.
 * No uploader controls, power lease, persistence or arbitrary command.
 * An outer timeout owns the lifetime; PROBE is claimed once by action.sh.
 */
#define DISPLAY_OBSERVER_ONLY
#define ROOT "/setting/a7c-debug/ram/ui-layout-once"
#define RAM ROOT
#define PORT 21217
#include "../debugger/listener.c"
