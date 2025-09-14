import Foundation
import SQLite3

class DatabaseService: ObservableObject {
    private var db: OpaquePointer?
    private let dbPath = Config.databasePath
    
    @Published var cases: [CaseModel] = []
    @Published var offers: [OfferModel] = []
    @Published var users: [UserModel] = []
    @Published var communications: [EmailCommunication] = []
    
    init() {
        openDatabase()
    }
    
    deinit {
        if db != nil {
            sqlite3_close(db)
        }
    }
    
    private func openDatabase() {
        if sqlite3_open(dbPath, &db) != SQLITE_OK {
            print("Unable to open database at path: \(dbPath)")
            if let errorPointer = sqlite3_errmsg(db) {
                let errorMessage = String(cString: errorPointer)
                print("Database error: \(errorMessage)")
            }
        } else {
            print("Successfully opened database at: \(dbPath)")
        }
    }
    
    // Helper function to safely get string from SQLite column
    private func getStringFromColumn(_ statement: OpaquePointer?, _ index: Int32) -> String {
        if let textPointer = sqlite3_column_text(statement, index) {
            return String(cString: textPointer)
        }
        return ""
    }
    
    func loadCases() {
        cases.removeAll()
        let queryString = "SELECT * FROM cases ORDER BY id DESC"
        
        var queryStatement: OpaquePointer?
        if sqlite3_prepare_v2(db, queryString, -1, &queryStatement, nil) == SQLITE_OK {
            while sqlite3_step(queryStatement) == SQLITE_ROW {
                let id = Int(sqlite3_column_int(queryStatement, 0))
                
                let subject = getStringFromColumn(queryStatement, 1)
                let features = getStringFromColumn(queryStatement, 2)
                let location = getStringFromColumn(queryStatement, 3)
                let budget = Double(sqlite3_column_double(queryStatement, 4))
                let timeline = getStringFromColumn(queryStatement, 5)
                let additionalFeatures = getStringFromColumn(queryStatement, 6)
                
                let caseModel = CaseModel(
                    id: id,
                    subject: subject,
                    features: features,
                    location: location,
                    budget: budget,
                    timeline: timeline,
                    additionalFeatures: additionalFeatures
                )
                cases.append(caseModel)
            }
        } else {
            print("SELECT statement could not be prepared")
        }
        sqlite3_finalize(queryStatement)
        print("Loaded \(cases.count) cases")
    }
    
    func loadOffers() {
        offers.removeAll()
        let queryString = "SELECT * FROM offers ORDER BY created_at DESC"
        
        var queryStatement: OpaquePointer?
        if sqlite3_prepare_v2(db, queryString, -1, &queryStatement, nil) == SQLITE_OK {
            while sqlite3_step(queryStatement) == SQLITE_ROW {
                let offerId = Int(sqlite3_column_int(queryStatement, 0))
                let caseId = Int(sqlite3_column_int(queryStatement, 1))
                
                let status = getStringFromColumn(queryStatement, 2)
                let price = Double(sqlite3_column_double(queryStatement, 3))
                let timeline = getStringFromColumn(queryStatement, 4)
                let accuracy = Double(sqlite3_column_double(queryStatement, 5))
                let additionalDetails = getStringFromColumn(queryStatement, 6)
                let vendorEmail = getStringFromColumn(queryStatement, 8)
                
                let offer = OfferModel(
                    offerId: offerId,
                    caseId: caseId,
                    status: status.isEmpty ? "pending" : status,
                    price: price,
                    timeline: timeline,
                    accuracy: accuracy,
                    additionalDetails: additionalDetails,
                    vendorEmail: vendorEmail
                )
                offers.append(offer)
            }
        } else {
            print("SELECT statement for offers could not be prepared")
        }
        sqlite3_finalize(queryStatement)
        print("Loaded \(offers.count) offers")
    }
    
    func loadUsers() {
        users.removeAll()
        let queryString = "SELECT * FROM users ORDER BY id DESC"
        
        var queryStatement: OpaquePointer?
        if sqlite3_prepare_v2(db, queryString, -1, &queryStatement, nil) == SQLITE_OK {
            while sqlite3_step(queryStatement) == SQLITE_ROW {
                let id = Int(sqlite3_column_int(queryStatement, 0))
                let caseId = Int(sqlite3_column_int(queryStatement, 1))
                
                let name = getStringFromColumn(queryStatement, 2)
                let email = getStringFromColumn(queryStatement, 3)
                let phone = getStringFromColumn(queryStatement, 4)
                
                let user = UserModel(
                    id: id,
                    caseId: caseId,
                    name: name,
                    email: email,
                    phone: phone
                )
                users.append(user)
            }
        }
        sqlite3_finalize(queryStatement)
        print("Loaded \(users.count) users")
    }
    
    func getCaseById(_ id: Int) -> CaseModel? {
        return cases.first { $0.id == id }
    }
    
    func refreshAll() {
        loadCases()
        loadOffers()
        loadUsers()
    }
}
