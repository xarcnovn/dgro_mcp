import Foundation
import SQLite3

final class SQLiteLiveStore: ObservableObject {
    @Published var cases: [[String: Any]] = []
    @Published var offers: [[String: Any]] = []
    @Published var emails: [[String: Any]] = []

    private var db: OpaquePointer?
    private let dbPath: String

    init(dbPath: String) {
        self.dbPath = dbPath
        open()
    }

    deinit {
        close()
    }

    func open() {
        if db != nil { return }
        if sqlite3_open(dbPath, &db) != SQLITE_OK {
            print("[SQLiteLiveStore] Failed to open DB at \(dbPath)")
            db = nil
        }
    }

    func close() {
        if let db = db {
            sqlite3_close(db)
            self.db = nil
        }
    }

    func refreshAll() {
        open()
        self.cases = fetchAll(from: "cases")
        self.offers = fetchAll(from: "offers")
        self.emails = fetchAll(from: "email_communications")
    }

    private func fetchAll(from table: String) -> [[String: Any]] {
        guard let db = db else { return [] }
        var statement: OpaquePointer?
        let sql = "SELECT * FROM \(table) ORDER BY rowid DESC"
        var rows: [[String: Any]] = []

        if sqlite3_prepare_v2(db, sql, -1, &statement, nil) != SQLITE_OK {
            if let cErr = sqlite3_errmsg(db) { print("[SQLiteLiveStore] prepare error: \(String(cString: cErr))") }
            return []
        }

        defer { sqlite3_finalize(statement) }

        let columnCount = sqlite3_column_count(statement)
        while sqlite3_step(statement) == SQLITE_ROW {
            var row: [String: Any] = [:]
            for i in 0..<columnCount {
                guard let nameC = sqlite3_column_name(statement, i) else { continue }
                let name = String(cString: nameC)
                let type = sqlite3_column_type(statement, i)
                switch type {
                case SQLITE_INTEGER:
                    row[name] = Int(sqlite3_column_int64(statement, i))
                case SQLITE_FLOAT:
                    row[name] = sqlite3_column_double(statement, i)
                case SQLITE_TEXT:
                    if let txt = sqlite3_column_text(statement, i) {
                        row[name] = String(cString: txt)
                    } else {
                        row[name] = nil as String?
                    }
                case SQLITE_NULL:
                    row[name] = NSNull()
                case SQLITE_BLOB:
                    if let bytes = sqlite3_column_blob(statement, i) {
                        let length = Int(sqlite3_column_bytes(statement, i))
                        row[name] = Data(bytes: bytes, count: length)
                    } else {
                        row[name] = Data()
                    }
                default:
                    row[name] = NSNull()
                }
            }
            rows.append(row)
        }

        return rows
    }
}


