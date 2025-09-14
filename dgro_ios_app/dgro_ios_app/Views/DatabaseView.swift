import SwiftUI

struct DatabaseView: View {
    @StateObject private var dbService = DatabaseService()
    @State private var selectedTab = 0
    @State private var selectedCase: CaseModel?
    @State private var selectedOffer: OfferModel?
    
    var body: some View {
        TabView(selection: $selectedTab) {
            // Cases Tab
            NavigationStack {
                List(dbService.cases) { caseItem in
                    NavigationLink(destination: CaseDetailView(caseModel: caseItem, dbService: dbService)) {
                        CaseRowView(caseModel: caseItem)
                    }
                }
                .navigationTitle("Cases")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button(action: refreshData) {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                }
                .refreshable {
                    refreshData()
                }
                .overlay {
                    if dbService.cases.isEmpty {
                        ContentUnavailableView(
                            "No Cases",
                            systemImage: "folder",
                            description: Text("Create cases through the chat interface")
                        )
                    }
                }
            }
            .tabItem {
                Label("Cases", systemImage: "folder.fill")
            }
            .tag(0)
            
            // Offers Tab
            NavigationStack {
                List(dbService.offers) { offer in
                    NavigationLink(destination: OfferDetailView(offer: offer, dbService: dbService)) {
                        OfferRowView(offer: offer, caseTitle: dbService.getCaseById(offer.caseId)?.subject ?? "Unknown Case")
                    }
                }
                .navigationTitle("Offers")
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button(action: refreshData) {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                }
                .refreshable {
                    refreshData()
                }
                .overlay {
                    if dbService.offers.isEmpty {
                        ContentUnavailableView(
                            "No Offers",
                            systemImage: "tag",
                            description: Text("Offers will appear here after vendor responses")
                        )
                    }
                }
            }
            .tabItem {
                Label("Offers", systemImage: "tag.fill")
            }
            .tag(1)
        }
        .task {
            refreshData()
        }
    }
    
    private func refreshData() {
        dbService.refreshAll()
    }
}

struct CaseRowView: View {
    let caseModel: CaseModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(caseModel.subject)
                .font(.headline)
                .lineLimit(1)
            
            HStack {
                Label("$\(caseModel.budget, specifier: "%.0f")", systemImage: "dollarsign.circle")
                    .font(.caption)
                    .foregroundColor(.green)
                
                Spacer()
                
                Label(caseModel.location, systemImage: "location")
                    .font(.caption)
                    .foregroundColor(.blue)
            }
            
            Text(caseModel.timeline)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}

struct OfferRowView: View {
    let offer: OfferModel
    let caseTitle: String
    
    var statusColor: Color {
        switch offer.status.lowercased() {
        case "active": return .green
        case "pending": return .orange
        case "accepted": return .blue
        case "rejected": return .red
        case "expired": return .gray
        default: return .gray
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(caseTitle)
                    .font(.headline)
                    .lineLimit(1)
                
                Spacer()
                
                Text(offer.status.capitalized)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(statusColor.opacity(0.2))
                    .foregroundColor(statusColor)
                    .cornerRadius(4)
            }
            
            HStack {
                Text("$\(offer.price, specifier: "%.0f")")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                
                Text("•")
                    .foregroundColor(.secondary)
                
                Text(offer.timeline)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            Text(offer.vendorEmail)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }
}
