// Graylog.app — cửa sổ native bọc trang quản lý của gl (gl-ui.py).
// Build: xem ~/.local/bin/gl-app-build
import Cocoa
import WebKit
import UserNotifications

final class Hand: NSButton {   // nút có con trỏ bàn tay khi rê chuột vào
    override func resetCursorRects() { addCursorRect(bounds, cursor: .pointingHand) }
}

// Một cửa sổ = một dải tab tự vẽ ở trên cùng + trang của tab đang chọn. Mỗi tab là một WKWebView riêng, tên tab = tên đối tác đang mở trong tab đó.
final class Win: NSObject {
    let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 900, height: 720),
                     styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
    let bar = NSStackView(), holder = NSView()
    var webs: [WKWebView] = [], obs: [NSKeyValueObservation] = [], sel = 0
    unowned let app: AppDelegate

    init(_ app: AppDelegate) {
        self.app = app
        super.init()
        w.title = "Graylog"; w.isReleasedWhenClosed = false; w.tabbingMode = .disallowed
        w.setFrameAutosaveName("main")
        let root = NSView()
        bar.orientation = .horizontal; bar.spacing = 6; bar.edgeInsets = NSEdgeInsets(top: 0, left: 10, bottom: 0, right: 10)
        for v in [bar, holder] as [NSView] { v.translatesAutoresizingMaskIntoConstraints = false; root.addSubview(v) }
        NSLayoutConstraint.activate([
            bar.topAnchor.constraint(equalTo: root.topAnchor), bar.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            bar.trailingAnchor.constraint(equalTo: root.trailingAnchor), bar.heightAnchor.constraint(equalToConstant: 40),
            holder.topAnchor.constraint(equalTo: bar.bottomAnchor), holder.bottomAnchor.constraint(equalTo: root.bottomAnchor),
            holder.leadingAnchor.constraint(equalTo: root.leadingAnchor), holder.trailingAnchor.constraint(equalTo: root.trailingAnchor)])
        w.contentView = root
    }

    func add(_ url: URL) {
        let web = WKWebView(frame: .zero)
        web.uiDelegate = app
        web.load(URLRequest(url: url))
        webs.append(web)
        obs.append(web.observe(\.title) { [weak self] _, _ in self?.draw() })
        select(webs.count - 1)
    }
    func select(_ i: Int) {
        sel = i
        holder.subviews.forEach { $0.removeFromSuperview() }
        webs[i].frame = holder.bounds; webs[i].autoresizingMask = [.width, .height]
        holder.addSubview(webs[i]); w.makeFirstResponder(webs[i])
        draw()
    }
    func close(_ i: Int) {
        if webs.count < 2 { w.performClose(nil); return }
        webs.remove(at: i).removeFromSuperview(); obs.remove(at: i)
        select(i < sel ? sel - 1 : min(sel, webs.count - 1))
    }
    @objc func pick(_ b: NSButton) { select(b.tag) }
    @objc func shut(_ b: NSButton) { close(b.tag) }
    @objc func plus(_ b: NSButton) { app.newTab(b) }

    func draw() {   // vẽ lại cả dải tab mỗi khi đổi tab / đổi tên trang; vài tab nên không cần tối ưu
        func name(_ v: WKWebView) -> String {   // "Graylog — <đối tác>" -> "<đối tác>"
            let t = (v.title ?? "").replacingOccurrences(of: "^Graylog( AI)? — ", with: "", options: .regularExpression)
            return t.isEmpty || t == "Graylog" ? "Đối tác" : t
        }
        func button(_ title: String, _ size: CGFloat, _ weight: NSFont.Weight, _ color: NSColor, _ action: Selector, _ tag: Int) -> NSButton {
            let b = Hand(title: "", target: self, action: action)
            b.isBordered = false; b.tag = tag; b.lineBreakMode = .byTruncatingTail
            b.attributedTitle = NSAttributedString(string: title, attributes: [.font: NSFont.systemFont(ofSize: size, weight: weight), .foregroundColor: color])
            return b
        }
        bar.views.forEach { bar.removeView($0) }
        for (i, v) in webs.enumerated() {
            let on = i == sel
            let t = button(name(v), 13, on ? .semibold : .regular, on ? .labelColor : .secondaryLabelColor, #selector(pick(_:)), i)
            t.widthAnchor.constraint(lessThanOrEqualToConstant: 200).isActive = true
            t.widthAnchor.constraint(greaterThanOrEqualToConstant: 70).isActive = true
            let x = button("✕", 10, .regular, .secondaryLabelColor, #selector(shut(_:)), i); x.toolTip = "Đóng tab (⌘W)"
            let chip = NSStackView(views: [t, x])
            chip.spacing = 4; chip.edgeInsets = NSEdgeInsets(top: 0, left: 12, bottom: 0, right: 9)
            chip.wantsLayer = true; chip.layer?.cornerRadius = 8
            // màu có độ trong suốt nên dùng được cho cả giao diện sáng lẫn tối
            chip.layer?.backgroundColor = (on ? NSColor.controlAccentColor.withAlphaComponent(0.28) : NSColor.gray.withAlphaComponent(0.14)).cgColor
            chip.layer?.borderWidth = on ? 1 : 0; chip.layer?.borderColor = NSColor.controlAccentColor.withAlphaComponent(0.7).cgColor
            chip.heightAnchor.constraint(equalToConstant: 28).isActive = true
            chip.setHuggingPriority(.required, for: .horizontal); t.setContentHuggingPriority(.required, for: .horizontal)   // tab rộng vừa tên, không giãn hết thanh
            bar.addView(chip, in: .leading)
        }
        let p = button("＋ Mở thêm đối tác", 13, .regular, .secondaryLabelColor, #selector(plus(_:)), 0); p.toolTip = "Mở tab mới để xem đối tác khác song song (⌘T)"   // ghi chữ rõ: người mới không biết phím ⌘T
        p.setContentHuggingPriority(.required, for: .horizontal)
        bar.addView(p, in: .leading)
        w.title = webs.isEmpty ? "Graylog" : name(webs[sel])
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, UNUserNotificationCenterDelegate {
    let bin = NSHomeDirectory() + "/.local/bin"
    var server: Process?
    var url: URL?
    var windows: [Win] = []

    // Server là tiến trình con: tắt app (đóng stdin của nó) là server tự thoát.
    func startServer() -> Bool {
        let p = Process(), out = Pipe()
        p.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        p.arguments = [bin + "/gl-ui.py", bin + "/gl", "app"]
        p.standardInput = Pipe(); p.standardOutput = out; p.standardError = FileHandle.nullDevice
        guard (try? p.run()) != nil else { return false }
        server = p
        var line = Data()
        while let b = Optional(out.fileHandleForReading.readData(ofLength: 1)), !b.isEmpty, b[0] != 10 { line += b }
        url = URL(string: String(decoding: line, as: UTF8.self))
        return url != nil
    }

    @objc func newTab(_ sender: Any?) {
        if let k = keyWin, let url = url { k.add(url) } else { newWindow(sender) }
    }
    @objc func closeTab(_ sender: Any?) {   // ⌘W: đóng tab đang xem; tab cuối cùng thì đóng cửa sổ
        if let k = keyWin { k.close(k.sel) } else { NSApp.keyWindow?.performClose(sender) }
    }
    @objc func nextTab(_ sender: Any?) { if let k = keyWin { k.select((k.sel + 1) % k.webs.count) } }
    @objc func prevTab(_ sender: Any?) { if let k = keyWin { k.select((k.sel + k.webs.count - 1) % k.webs.count) } }
    var keyWin: Win? { windows.first { $0.w == NSApp.keyWindow } }

    @objc func newWindow(_ sender: Any?) {
        if server?.isRunning != true { _ = startServer() }
        guard let url = url else { return }
        let n = Win(self)
        if let last = windows.last(where: { $0.w.isVisible }) {   // cửa sổ mới lệch một chút so với cửa sổ trước
            n.w.setFrameTopLeftPoint(NSPoint(x: last.w.frame.minX + 28, y: last.w.frame.maxY - 28))
        } else if !n.w.setFrameUsingName("main") { n.w.center() }
        n.add(url)
        windows = windows.filter { $0.w.isVisible } + [n]
        n.w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func applicationDidFinishLaunching(_ n: Notification) {
        let main = NSMenu()
        func menu(_ title: String, _ items: [(String, Selector, String)]) {
            let m = NSMenu(title: title)
            for (t, s, k) in items { m.addItem(withTitle: t, action: s, keyEquivalent: k) }
            let i = NSMenuItem(); i.submenu = m; main.addItem(i)
        }
        menu("Graylog", [("Settings…", #selector(openSettings(_:)), ","),
                         ("Hide Graylog", #selector(NSApplication.hide(_:)), "h"),
                         ("Quit Graylog", #selector(NSApplication.terminate(_:)), "q")])
        menu("File", [("New Tab", #selector(newTab(_:)), "t"), ("New Window", #selector(newWindow(_:)), "n"),
                      ("Close Tab", #selector(closeTab(_:)), "w")])
        menu("Edit", [("Undo", Selector(("undo:")), "z"), ("Cut", #selector(NSText.cut(_:)), "x"),
                      ("Copy", #selector(NSText.copy(_:)), "c"), ("Paste", #selector(NSText.paste(_:)), "v"),
                      ("Select All", #selector(NSText.selectAll(_:)), "a")])
        menu("View", [("Reload", #selector(WKWebView.reload(_:)), "r"),
                      ("Back", #selector(WKWebView.goBack(_:)), "["), ("Forward", #selector(WKWebView.goForward(_:)), "]"),
                      ("Next Tab", #selector(nextTab(_:)), "}"), ("Previous Tab", #selector(prevTab(_:)), "{")])
        NSApp.mainMenu = main
        UNUserNotificationCenter.current().delegate = self
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
        Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { _ in self.checkAnswers() }
        guard startServer() else {
            let a = NSAlert(); a.messageText = "Không khởi động được gl-ui.py"; a.runModal(); NSApp.terminate(nil); return
        }
        checkAnswers()   // áp giao diện Sáng/Tối đã lưu trước khi mở cửa sổ
        newWindow(nil)
    }

    @objc func openSettings(_ sender: Any?) {   // mở hộp cài đặt của trang (nút bánh răng)
        if keyWin == nil { newWindow(nil) }
        if let k = keyWin { k.webs[k.sel].evaluateJavaScript("document.getElementById('cfg')?.click()") }
    }

    // Bấm icon trên Dock: quay lại cửa sổ đang có; chỉ tạo mới khi đã đóng hết.
    func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows: Bool) -> Bool {
        if !hasVisibleWindows { newWindow(nil) }
        return true
    }
    func applicationDockMenu(_ s: NSApplication) -> NSMenu? {
        let m = NSMenu(); m.addItem(withTitle: "New Tab", action: #selector(newTab(_:)), keyEquivalent: ""); m.addItem(withTitle: "New Window", action: #selector(newWindow(_:)), keyEquivalent: ""); return m
    }
    func applicationWillTerminate(_ n: Notification) { server?.terminate() }

    // AI chạy ngầm ghi mỗi câu trả lời ra ~/.config/gl/ask/<stamp>.html. Có file mới: hiện thông báo mang tên và icon của app.
    // (Không để trang web tự báo: WKWebView hãm timer của cửa sổ bị che nên trang không biết AI đã xong.)
    // đang ở trong app cũng hiện thông báo (mặc định macOS giấu thông báo của app đang đứng trước)
    func userNotificationCenter(_ c: UNUserNotificationCenter, willPresent n: UNNotification,
                                withCompletionHandler done: @escaping (UNNotificationPresentationOptions) -> Void) { done([.banner, .sound]) }
    var seen: Set<String>?
    func checkAnswers() {
        let th = ((try? String(contentsOfFile: NSHomeDirectory() + "/.config/gl/theme", encoding: .utf8)) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let ap = th == "dark" ? NSAppearance(named: .darkAqua) : th == "light" ? NSAppearance(named: .aqua) : nil
        if NSApp.appearance?.name != ap?.name { NSApp.appearance = ap }
        let dir = NSHomeDirectory() + "/.config/gl/ask"
        let all = (try? FileManager.default.contentsOfDirectory(atPath: dir)) ?? []
        func note(_ id: String, _ title: String, _ body: String) {
            let n = UNMutableNotificationContent(); n.sound = .default; n.title = title; n.body = String(body.prefix(140))
            UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: n, trigger: nil))
        }
        for f in all where f.hasSuffix(".note") {   // kết quả "Lưu và kiểm tra" ở Cài đặt AI, do gl-ui.py ghi
            let t = (try? String(contentsOfFile: dir + "/" + f, encoding: .utf8)) ?? ""
            try? FileManager.default.removeItem(atPath: dir + "/" + f)
            note(f, "Kiểm tra AI xong", t)
        }
        let now = Set(all.filter { $0.hasSuffix(".html") })
        defer { seen = now }
        guard let old = seen else { return }
        for f in now.subtracting(old) {
            let raw = (try? String(contentsOfFile: dir + "/" + f, encoding: .utf8)) ?? ""
            var text = raw.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
            for (k, v) in [("&lt;", "<"), ("&gt;", ">"), ("&quot;", "\""), ("&#x27;", "'"), ("&amp;", "&")] { text = text.replacingOccurrences(of: k, with: v) }
            text = text.replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression).trimmingCharacters(in: .whitespaces)
            note(f, raw.contains("<!--fail-->") ? "AI không trả lời được" : "AI đã trả lời xong", text)
        }
    }

    // confirm()/alert() của trang (vd: hỏi lại khi Xoá)
    func webView(_ v: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo,
                 completionHandler done: @escaping (Bool) -> Void) {
        let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "OK"); a.addButton(withTitle: "Huỷ")
        done(a.runModal() == .alertFirstButtonReturn)
    }
    func webView(_ v: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo,
                 completionHandler done: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = m; a.runModal(); done()
    }
    // <input type=file> (nút 📎 ở khung chat AI): WKWebView không tự mở hộp chọn file
    func webView(_ v: WKWebView, runOpenPanelWith p: WKOpenPanelParameters, initiatedByFrame f: WKFrameInfo,
                 completionHandler done: @escaping ([URL]?) -> Void) {
        let o = NSOpenPanel(); o.allowsMultipleSelection = p.allowsMultipleSelection
        done(o.runModal() == .OK ? o.urls : nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
