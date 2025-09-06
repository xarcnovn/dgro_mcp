import SwiftUI

struct DataView: View {
    @EnvironmentObject private var mcpManager: MCPClientManager
    @StateObject private var store = MockStore()
    @State private var searchText: String = ""

    var filteredCases: [CaseItem] {
        guard !searchText.isEmpty else { return store.cases }
        return store.cases.filter { $0.title.localizedCaseInsensitiveContains(searchText) || $0.summary.localizedCaseInsensitiveContains(searchText) }
    }

    var filteredOffers: [OfferItem] {
        guard !searchText.isEmpty else { return store.offers }
        return store.offers.filter { $0.title.localizedCaseInsensitiveContains(searchText) || $0.details.localizedCaseInsensitiveContains(searchText) }
    }

    var body: some View {
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
                Section("Cases") {
                    ForEach(filteredCases) { item in
                        NavigationLink(value: item) {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(item.title).font(.headline)
                                    Spacer()
                                    Text(item.createdAt, style: .date)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Text(item.summary).foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }

                Section("Offers") {
                    ForEach(filteredOffers) { offer in
                        NavigationLink(value: offer) {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(offer.title).font(.headline)
                                    Text(offer.details).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(offer.value)
                                    .font(.subheadline.weight(.semibold))
                                    .padding(6)
                                    .background(Color(.systemGray6))
                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
            }
            .searchable(text: $searchText)
            .navigationTitle("Data")
            .navigationDestination(for: CaseItem.self) { item in
                CaseDetailView(item: item)
            }
            .navigationDestination(for: OfferItem.self) { offer in
                OfferDetailView(item: offer)
            }
        }
    }
}

private struct CaseDetailView: View {
    let item: CaseItem
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(item.title).font(.largeTitle.bold())
            Text(item.summary).font(.body)
            Spacer()
        }
        .padding()
        .navigationTitle("Case")
    }
}

private struct OfferDetailView: View {
    let item: OfferItem
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(item.title).font(.largeTitle.bold())
            Text(item.details)
            HStack {
                Text("Value:").foregroundStyle(.secondary)
                Text(item.value).font(.title3.weight(.semibold))
            }
            Spacer()
        }
        .padding()
        .navigationTitle("Offer")
    }
}

struct DataView_Previews: PreviewProvider {
    static var previews: some View {
        DataView()
    }
}


