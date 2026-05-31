import AppKit
import Foundation

let pasteboardType = NSPasteboard.PasteboardType("com.goodnotesapp.goodnotes5.notes")
let outputPath = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "goodnotes_clipboard_item0.bin"

let pasteboard = NSPasteboard.general
guard let data = pasteboard.data(forType: pasteboardType) else {
    fputs("GoodNotes pasteboard type was not found.\n", stderr)
    exit(2)
}

let outputURL = URL(fileURLWithPath: outputPath)
do {
    try data.write(to: outputURL)
    print(outputURL.path)
} catch {
    fputs("Failed to write pasteboard data: \(error)\n", stderr)
    exit(3)
}

