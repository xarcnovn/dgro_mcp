import SwiftUI

struct CaseDetailView: View {
    let caseModel: CaseModel
    let dbService: DatabaseService
    
    var relatedOffers: [OfferModel] {
        dbService.offers.filter { $0.caseId == caseModel.id }
    }
    
    var relatedUser: UserModel? {
        dbService.users.first { $0.caseId == caseModel.id }
    }
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Case Info Section
                VStack(alignment: .leading, spacing: 12) {
                    Label("Case Information", systemImage: "info.circle.fill")
                        .font(.headline)
                        .foregroundColor(.blue)
                    
                    GroupBox {
                        VStack(alignment: .leading, spacing: 8) {
                            DetailRow(label: "Subject", value: caseModel.subject)
                            Divider()
                            DetailRow(label: "Location", value: caseModel.location)
                            Divider()
                            DetailRow(label: "Budget", value: "$\(caseModel.budget, specifier: "%.2f")")
                            Divider()
                            DetailRow(label: "Timeline", value: caseModel.timeline)
                        }
                    }
                }
                
                // Features Section
                if !caseModel.features.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Features", systemImage: "star.fill")
                            .font(.headline)
                            .foregroundColor(.orange)
                        
                        GroupBox {
                            Text(caseModel.features)
                                .font(.body)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                
                // Additional Features Section
                if !caseModel.additionalFeatures.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Additional Features", systemImage: "plus.circle.fill")
                            .font(.headline)
                            .foregroundColor(.purple)
                        
                        GroupBox {
                            Text(caseModel.additionalFeatures)
                                .font(.body)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                
                // User Info Section
                if let user = relatedUser {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Contact Information", systemImage: "person.circle.fill")
                            .font(.headline)
                            .foregroundColor(.green)
                        
                        GroupBox {
                            VStack(alignment: .leading, spacing: 8) {
                                DetailRow(label: "Name", value: user.name)
                                Divider()
                                DetailRow(label: "Email", value: user.email)
                                Divider()
                                DetailRow(label: "Phone", value: user.phone)
                            }
                        }
                    }
                }
                
                // Related Offers Section
                if !relatedOffers.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Related Offers (\(relatedOffers.count))", systemImage: "tag.fill")
                            .font(.headline)
                            .foregroundColor(.indigo)
                        
                        ForEach(relatedOffers) { offer in
                            NavigationLink(destination: OfferDetailView(offer: offer, dbService: dbService)) {
                                GroupBox {
                                    HStack {
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(offer.vendorEmail)
                                                .font(.subheadline)
                                                .fontWeight(.medium)
                                            Text("$\(offer.price, specifier: "%.0f") • \(offer.timeline)")
                                                .font(.caption)
                                                .foregroundColor(.secondary)
                                        }
                                        Spacer()
                                        Text(offer.status.capitalized)
                                            .font(.caption)
                                            .padding(.horizontal, 8)
                                            .padding(.vertical, 2)
                                            .background(statusColor(for: offer.status).opacity(0.2))
                                            .foregroundColor(statusColor(for: offer.status))
                                            .cornerRadius(4)
                                    }
                                }
                            }
                            .buttonStyle(PlainButtonStyle())
                        }
                    }
                }
            }
            .padding()
        }
        .navigationTitle("Case #\(caseModel.id)")
        .navigationBarTitleDisplayMode(.large)
    }
    
    private func statusColor(for status: String) -> Color {
        switch status.lowercased() {
        case "active": return .green
        case "pending": return .orange
        case "accepted": return .blue
        case "rejected": return .red
        case "expired": return .gray
        default: return .gray
        }
    }
}

struct DetailRow: View {
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .font(.body)
                .multilineTextAlignment(.trailing)
        }
    }
}
