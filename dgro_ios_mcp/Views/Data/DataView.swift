import SwiftUI

struct DBRow: Identifiable, Hashable {
    let id: String
    let table: String
    let data: [String: AnyHashable]
}

struct DataView: View {
    @EnvironmentObject private var mcpManager: MCPClientManager
    @StateObject private var sqliteStore: SQLiteLiveStore = {
        // Try bundled DB first, then absolute path as a dev fallback
        if let path = Bundle.main.path(forResource: "case_search", ofType: "db") {
            return SQLiteLiveStore(dbPath: path)
        } else {
            return SQLiteLiveStore(dbPath: "/Users/karol/final_mcp_september/case_search.db")
        }
    }()
    @State private var searchText: String = ""
    @State private var timer = Timer.publish(every: 4, on: .main, in: .common).autoconnect()

    private func stringify(_ value: Any) -> String {
        switch value {
        case let s as String: return s
        case let n as NSNumber: return n.stringValue
        case let d as Double: return String(d)
        case let i as Int: return String(i)
        case let data as Data: return "<" + String(data.count) + " bytes>"
        case _ as NSNull: return "—"
        default:
            return String(describing: value)
        }
    }

    private func toDBRows(_ table: String, rows: [[String: Any]]) -> [DBRow] {
        return rows.map { dict in
            let idCandidate: String = {
                if let idVal = dict["id"] { return stringify(idVal) }
                if let uuidVal = dict["uuid"] { return stringify(uuidVal) }
                let joined = dict.keys.sorted().map { "\($0)=\(stringify(dict[$0] ?? ""))" }.joined(separator: "|")
                return String(joined.hashValue)
            }()
            var hashable: [String: AnyHashable] = [:]
            for (k, v) in dict { hashable[k] = stringify(v) as AnyHashable }
            return DBRow(id: idCandidate, table: table, data: hashable)
        }
    }

    private func filter(_ rows: [DBRow]) -> [DBRow] {
        guard !searchText.isEmpty else { return rows }
        return rows.filter { row in
            row.data.contains { key, value in
                key.localizedCaseInsensitiveContains(searchText) || String(describing: value).localizedCaseInsensitiveContains(searchText)
            }
        }
    }

    var body: some View {
        let caseRows = filter(toDBRows("cases", rows: sqliteStore.cases))
        let offerRows = filter(toDBRows("offers", rows: sqliteStore.offers))
        let emailRows = filter(toDBRows("email_communications", rows: sqliteStore.emails))

        NavigationStack {
            List {
                Section("MCP") {
                    HStack {
                        Circle()
                            .fill(mcpManager.isConnected ? Color.green : Color.red)
                            .frame(width: 10, height: 10)
                        Text(mcpManager.statusMessage)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Section(header: sectionHeader(title: "Cases", count: caseRows.count)) {
                    if caseRows.isEmpty {
                        placeholder("No cases found")
                    } else {
                        ForEach(caseRows) { row in
                            NavigationLink(value: row) {
                                DBRowSummary(row: row)
                            }
                        }
                    }
                }

                Section(header: sectionHeader(title: "Offers", count: offerRows.count)) {
                    if offerRows.isEmpty {
                        placeholder("No offers found")
                    } else {
                        ForEach(offerRows) { row in
                            NavigationLink(value: row) {
                                DBRowSummary(row: row)
                            }
                        }
                    }
                }

                Section(header: sectionHeader(title: "Email communications", count: emailRows.count)) {
                    if emailRows.isEmpty {
                        placeholder("No emails found")
                    } else {
                        ForEach(emailRows) { row in
                            NavigationLink(value: row) {
                                DBRowSummary(row: row)
                            }
                        }
                    }
                }
            }
            .searchable(text: $searchText)
            .navigationTitle("Data")
            .refreshable { sqliteStore.refreshAll() }
            .onAppear { sqliteStore.refreshAll() }
            .onReceive(timer) { _ in sqliteStore.refreshAll() }
            .navigationDestination(for: DBRow.self) { row in
                DBRowDetail(row: row)
            }
        }
    }

    private func sectionHeader(title: String, count: Int) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text("\(count)")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Color(.systemGray6))
                .clipShape(Capsule())
        }
    }

    private func placeholder(_ text: String) -> some View {
        Text(text).foregroundStyle(.secondary)
    }
}

private struct DBRowSummary: View {
    let row: DBRow
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let title = preferredTitle(from: row.data) {
                Text(title).font(.headline)
            }
            KeyValueList(data: row.data)
        }
        .padding(.vertical, 6)
    }

    private func preferredTitle(from data: [String: AnyHashable]) -> String? {
        for key in ["title", "subject", "name", "case_title"] {
            if let v = data[key] { return String(describing: v) }
        }
        return nil
    }
}

private struct KeyValueList: View {
    let data: [String: AnyHashable]
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(data.keys.sorted(), id: \.self) { key in
                if let value = data[key] {
                    LabeledContent(key.capitalized) {
                        Text(String(describing: value))
                            .multilineTextAlignment(.trailing)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
}

private struct DBRowDetail: View {
    let row: DBRow
    var body: some View {
        List {
            Section("\(row.table.capitalized) item") {
                KeyValueList(data: row.data)
            }
        }
        .navigationTitle(row.table.capitalized)
    }
}

struct DataView_Previews: PreviewProvider {
    static var previews: some View {
        DataView()
    }
}

