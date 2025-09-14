import Foundation

struct OfferModel: Identifiable {
    let id = UUID()
    let offerId: Int
    let caseId: Int
    let status: String
    let price: Double
    let timeline: String
    let accuracy: Double
    let additionalDetails: String
    let vendorEmail: String
}
