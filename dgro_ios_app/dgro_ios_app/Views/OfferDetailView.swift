import SwiftUI

struct OfferDetailView: View {
    let offer: OfferModel
    let dbService: DatabaseService
    
    var relatedCase: CaseModel? {
        dbService.getCaseById(offer.caseId)
    }
    
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
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Status Badge
                HStack {
                    Spacer()
                    Text(offer.status.uppercased())
                        .font(.headline)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(statusColor.opacity(0.2))
                        .foregroundColor(statusColor)
                        .cornerRadius(8)
                    Spacer()
                }
                
                // Offer Info Section
                VStack(alignment: .leading, spacing: 12) {
                    Label("Offer Details", systemImage: "tag.circle.fill")
                        .font(.headline)
                        .foregroundColor(.indigo)
                    
                    GroupBox {
                        VStack(alignment: .leading, spacing: 8) {
                            DetailRow(label: "Offer ID", value: "#\(offer.offerId)")
                            Divider()
                            DetailRow(label: "Price", value: "$\(offer.price, specifier: "%.2f")")
                            Divider()
                            DetailRow(label: "Timeline", value: offer.timeline)
                            Divider()
                            DetailRow(label: "Accuracy", value: "\(offer.accuracy, specifier: "%.1f")%")
                        }
                    }
                }
                
                // Vendor Info Section
                VStack(alignment: .leading, spacing: 12) {
                    Label("Vendor Information", systemImage: "person.crop.circle.fill")
                        .font(.headline)
                        .foregroundColor(.blue)
                    
                    GroupBox {
                        VStack(alignment: .leading, spacing: 8) {
                            DetailRow(label: "Email", value: offer.vendorEmail)
                        }
                    }
                }
                
                // Additional Details Section
                if !offer.additionalDetails.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Additional Details", systemImage: "doc.text.fill")
                            .font(.headline)
                            .foregroundColor(.purple)
                        
                        GroupBox {
                            Text(offer.additionalDetails)
                                .font(.body)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                
                // Related Case Section
                if let caseModel = relatedCase {
                    VStack(alignment: .leading, spacing: 12) {
                        Label("Related Case", systemImage: "folder.fill")
                            .font(.headline)
                            .foregroundColor(.orange)
                        
                        NavigationLink(destination: CaseDetailView(caseModel: caseModel, dbService: dbService)) {
                            GroupBox {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(caseModel.subject)
                                        .font(.subheadline)
                                        .fontWeight(.medium)
                                    HStack {
                                        Text("Budget: $\(caseModel.budget, specifier: "%.0f")")
                                            .font(.caption)
                                        Spacer()
                                        Text(caseModel.location)
                                            .font(.caption)
                                    }
                                    .foregroundColor(.secondary)
                                }
                            }
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
                
                // Action Buttons
                VStack(spacing: 12) {
                    if offer.status.lowercased() == "pending" || offer.status.lowercased() == "active" {
                        Button(action: {
                            // TODO: Implement accept offer via MCP
                        }) {
                            Label("Accept Offer", systemImage: "checkmark.circle.fill")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                        
                        Button(action: {
                            // TODO: Implement reject offer via MCP
                        }) {
                            Label("Reject Offer", systemImage: "xmark.circle.fill")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.large)
                        .tint(.red)
                    }
                }
                .padding(.top)
            }
            .padding()
        }
        .navigationTitle("Offer #\(offer.offerId)")
        .navigationBarTitleDisplayMode(.large)
    }
}
