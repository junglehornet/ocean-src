/* Native fixture: process APIs should not depend on a shell's startup behavior. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <direct.h>
#define getcwd _getcwd
#else
#include <unistd.h>
#endif
static int execute(int argc, char **argv) {
    if (argc < 2) return 2;
    if (!strcmp(argv[1], "output")) { fputs("native-output", stdout); return 0; }
    if (!strcmp(argv[1], "exit")) return 7;
    if (!strcmp(argv[1], "large")) { for (int i=0;i<160000;i++) putchar('x'); return 0; }
    if (!strcmp(argv[1], "args")) {
        for (int i=2;i<argc;i++) { if(i>2) putchar('|'); fputs(argv[i],stdout); }
        return 0;
    }
    if (!strcmp(argv[1], "environment") && argc == 3) {
        char cwd[32768]; if (!getcwd(cwd,sizeof(cwd))) return 3;
        for (char *p=cwd;*p;p++) if (*p=='\\') *p='/';
        for (char *p=argv[2];*p;p++) if (*p=='\\') *p='/';
#ifdef _WIN32
        if (_stricmp(cwd,argv[2])) return 4;
#else
        if (strcmp(cwd,argv[2])) return 4;
#endif
        const char *value=getenv("OCEAN_EXEC_TEST");
        if (!value) return 5;
        printf("%s|cwd-ok",value); return 0;
    }
    return 6;
}
#ifdef _WIN32
int wmain(int argc, wchar_t **wide) {
    char **argv=calloc((size_t)argc+1,sizeof(*argv)); if (!argv) return 8;
    for(int i=0;i<argc;i++) {
        int n=WideCharToMultiByte(CP_UTF8,0,wide[i],-1,NULL,0,NULL,NULL);
        argv[i]=malloc(n); if(!argv[i]) return 8;
        WideCharToMultiByte(CP_UTF8,0,wide[i],-1,argv[i],n,NULL,NULL);
    }
    int status=execute(argc,argv);
    for(int i=0;i<argc;i++)free(argv[i]); free(argv); return status;
}
#else
int main(int argc,char **argv) { return execute(argc,argv); }
#endif
