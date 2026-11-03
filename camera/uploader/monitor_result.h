/* strstr must be declared by the caller (camera ABI or host string.h). */
static int a7c_command_result(int is_copy,const char *response) {
 if(!is_copy)return 0;
 return (strstr(response,"Can't open file ") ||
         strstr(response,"Can\\'t open file ") ||
         strstr(response,"illegal file name ")) ? 73 : 0;
}

/* The marker for echoed commands includes native CRLF, never local LF echo. */
static const char *a7c_completed_reply(const char *response,const char *marker,const char *prompt) {
 const char *m=strstr(response,marker);
 return m && strstr(m+strlen(marker),prompt) ? m : (const char *)0;
}
