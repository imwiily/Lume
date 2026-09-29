import SwiftUI
import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationWillTerminate(_ notification: Notification) {
        PythonRunner.shared.cancel()
    }
}

@main
@MainActor
struct LumeApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var store = ReviewStore()

    var body: some Scene {
        Window("Lume · Revisão editorial", id: "main") {
            ContentView().environmentObject(store)
                .frame(minWidth: 1040, minHeight: 680)
        }
        .defaultSize(width: 1280, height: 820)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Escolher manuscrito…") { store.chooseDocument() }
                    .keyboardShortcut("o").disabled(store.isBusy)
                Button("Abrir relatório JSON…") { store.chooseReport() }
                    .keyboardShortcut("o", modifiers: [.command, .shift]).disabled(store.isBusy)
            }
            CommandGroup(after: .saveItem) {
                Button("Exportar decisões…") { store.exportDecisions() }
                    .keyboardShortcut("s").disabled(store.report == nil || store.isBusy)
            }
        }
    }
}
