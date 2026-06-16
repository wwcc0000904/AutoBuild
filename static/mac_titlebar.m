#import <Cocoa/Cocoa.h>

void fix_titlebar(void *ns_window_ptr) {
    NSWindow *win = (__bridge NSWindow *)ns_window_ptr;
    if (!win) return;

    // 标题栏透明
    win.titlebarAppearsTransparent = YES;

    // 全尺寸内容视图：内容扩展到标题栏区域（类似 WorkBuddy）
    win.styleMask |= NSWindowStyleMaskFullSizeContentView;

    // 隐藏标题文字
    win.titleVisibility = NSWindowTitleHidden;

    // 强制浅色外观
    win.appearance = [NSAppearance appearanceNamed:NSAppearanceNameAqua];

    // 背景色统一（蓝灰 #e0e3ed）
    win.backgroundColor = [NSColor colorWithCalibratedRed:0.878 green:0.890 blue:0.929 alpha:1.0];
}
