/* Offline marker module. No threads, files, hardware or graphics. */
extern void lab_event(unsigned);
__attribute__((constructor)) static void loaded(void) { lab_event(1); }
__attribute__((destructor)) static void unloaded(void) { lab_event(4); }
int a7c_module_init(void) { lab_event(2); return -17; }
int a7c_module_exit(void) { lab_event(3); return -19; }
/* Native descriptor symbols for the separate, private path-only trial. */
int IM_SAMPLE_SO_init(void) { return a7c_module_init(); }
int IM_SAMPLE_SO_exit(void) { return a7c_module_exit(); }
int IM_SAMPLE_SO_sus(void) { return 0; }
int IM_SAMPLE_SO_res(void) { return 0; }
int IM_SAMPLE_SO_inact(void) { return 0; }
int IM_SAMPLE_SO_act(void) { return 0; }
