#import <Cocoa/Cocoa.h>
#import <objc/runtime.h>

int main(int argc, const char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: set_mac_titlebar <window_title>\n");
        return 1;
    }
    
    @autoreleasepool {
        NSString *targetTitle = [NSString stringWithUTF8String:argv[1]];
        
        // Force NSApplication to initialize
        [NSApplication sharedApplication];
        
        // Wait briefly for windows to appear
        usleep(200000);
        
        for (NSWindow *window in [NSApplication sharedApplication].windows) {
            if ([window.title containsString:targetTitle] || 
                [window.title isEqualToString:targetTitle]) {
                
                // 1. 标题栏透明
                window.titlebarAppearsTransparent = YES;
                
                // 2. 全尺寸内容视图（内容延伸到标题栏）
                window.styleMask |= NSWindowStyleMaskFullSizeContentView;
                
                // 3. 强制浅色外观
                window.appearance = [NSAppearance appearanceNamed:NSAppearanceNameAqua];
                
                fprintf(stdout, "OK: styled window '%s'\n", [window.title UTF8String]);
                return 0;
            }
        }
        
        // List available windows for debugging
        fprintf(stderr, "Window '%s' not found. Available:\n", argv[1]);
        for (NSWindow *w in [NSApplication sharedApplication].windows) {
            fprintf(stderr, "  - '%s'\n", [w.title UTF8String]);
        }
        return 1;
    }
}
