import Foundation
import SQLite3

final class SQLiteLiveStore: ObservableObject {
    @Published var cases: [[String: Any]] = []
    @Published var offers: [[String: Any]] = []
    @Published var emails: [[String: Any]] = []
    @Published var status: String = "Initializing"

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
        let rc = sqlite3_open(dbPath, &db)
        if rc != SQLITE_OK {
            let err = db.flatMap { sqlite3_errmsg($0) }.map { String(cString: $0) } ?? "unknown"
            status = "Open failed: \(err) @ \(dbPath)"
            print("[SQLiteLiveStore] Failed to open DB at \(dbPath): rc=\(rc) \(err)")
            db = nil
        } else {
            status = "Opened: \(dbPath)"
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
        let c = fetchAll(from: "cases")
        let o = fetchAll(from: "offers")
        let e = fetchAll(from: "email_communications")
        DispatchQueue.main.async {
            self.cases = c
            self.offers = o
            self.emails = e
            self.status = "Cases: \(c.count), Offers: \(o.count), Emails: \(e.count)"
        }
    }

    private func fetchAll(from table: String) -> [[String: Any]] {
        guard let db = db else { return [] }
        var statement: OpaquePointer?
        let sql = "SELECT * FROM \(table) ORDER BY rowid DESC"
        var rows: [[String: Any]] = []

        if sqlite3_prepare_v2(db, sql, -1, &statement, nil) != SQLITE_OK {
            if let cErr = sqlite3_errmsg(db) { print("[SQLiteLiveStore] prepare error for table \(table): \(String(cString: cErr))") }
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


