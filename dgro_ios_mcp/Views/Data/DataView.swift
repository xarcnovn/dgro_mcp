import SwiftUI

struct DataView: View {
    @StateObject private var store = MockStore()
    @State private var searchText: String = ""

    var filteredCases: [CaseItem] {
        guard !searchText.isEmpty else { return store.cases }
        return store.cases.filter { $0.title.localizedCaseInsensitiveContains(searchText) || $0.summary.localizedCaseInsensitiveContains(searchText) }
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(filteredCases) { item in
                        NavigationLink(value: item) {
                            CaseRowView(item: item)
                        }
                        .listRowSeparator(.hidden)
                        .listRowBackground(Color.clear)
                    }
                } header: {
                    Text("Cases")
                }
            }
            .listStyle(.insetGrouped)
            .searchable(text: $searchText)
            .navigationTitle("Cases")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: CaseItem.self) { item in
                CaseDetailView(item: item)
            }
        }
    }
}

private struct CaseRowView: View {
    let item: CaseItem

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(item.title)
                    .font(.headline)
                    .lineLimit(1)
                Spacer(minLength: 8)
                Text(item.createdAt, style: .date)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(item.summary)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(2)

            HStack(spacing: 12) {
                Label("0", systemImage: "tag.fill")
                    .font(.caption)
                    .padding(.vertical, 6)
                    .padding(.horizontal, 10)
                    .background(Color(.systemGray6))
                    .clipShape(Capsule())

                Label("0", systemImage: "bubble.left.and.bubble.right.fill")
                    .font(.caption)
                    .padding(.vertical, 6)
                    .padding(.horizontal, 10)
                    .background(Color(.systemGray6))
                    .clipShape(Capsule())

                Spacer()
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(.secondarySystemGroupedBackground))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .stroke(Color(.separator).opacity(0.2), lineWidth: 1)
        )
    }
}

private struct CaseDetailView: View {
    let item: CaseItem
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(alignment: .firstTextBaseline) {
                    Text(item.title)
                        .font(.largeTitle.bold())
                        .lineLimit(2)
                    Spacer()
                }

                Text(item.createdAt, style: .date)
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Text(item.summary)
                    .font(.body)
                    .foregroundStyle(.primary)

                HStack(spacing: 16) {
                    Label("0 Offers", systemImage: "tag.fill")
                        .font(.subheadline)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 12)
                        .background(Color(.systemGray6))
                        .clipShape(Capsule())
                    Label("0 Messages", systemImage: "bubble.left.and.bubble.right.fill")
                        .font(.subheadline)
                        .padding(.vertical, 8)
                        .padding(.horizontal, 12)
                        .background(Color(.systemGray6))
                        .clipShape(Capsule())
                    Spacer()
                }
            }
            .padding()
        }
        .navigationTitle("Case")
    }
}

struct DataView_Previews: PreviewProvider {
    static var previews: some View {
        DataView()
    }
}
