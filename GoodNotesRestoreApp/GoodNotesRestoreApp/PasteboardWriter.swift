import Foundation
import UIKit

enum PasteboardWriter {
    static let goodNotesPasteboardType = "com.goodnotesapp.goodnotes5.notes"

    static func writeGoodNotesBinary(_ data: Data) {
        UIPasteboard.general.items = [
            [
                goodNotesPasteboardType: data
            ]
        ]
    }
}
