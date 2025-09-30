<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DGRO MVP - Simple Vendor Discovery</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f9fafb;
            color: #111827;
            line-height: 1.6;
        }
        
        /* Simple Header */
        .header {
            background: white;
            border-bottom: 1px solid #e5e7eb;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            color: #6366f1;
        }
        
        .new-case-btn {
            padding: 0.625rem 1.25rem;
            background: #6366f1;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
        }
        
        .new-case-btn:hover {
            background: #4f46e5;
        }
        
        /* Container */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        /* Page Title */
        .page-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 2rem;
            color: #111827;
        }
        
        /* View Toggle */
        .view-toggle {
            display: none;
        }
        
        /* PAGE 1: CASES LIST */
        .cases-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1.5rem;
        }
        
        .case-card {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1.5rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .case-card:hover {
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            transform: translateY(-2px);
            border-color: #6366f1;
        }
        
        .case-status {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 0.75rem;
        }
        
        .status-active {
            background: #d1fae5;
            color: #065f46;
        }
        
        .status-complete {
            background: #dbeafe;
            color: #1e40af;
        }
        
        .case-title {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
            color: #111827;
        }
        
        .case-info {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            margin-bottom: 1rem;
            font-size: 0.875rem;
            color: #6b7280;
        }
        
        .case-footer {
            display: flex;
            justify-content: space-between;
            padding-top: 1rem;
            border-top: 1px solid #f3f4f6;
            font-size: 0.875rem;
        }
        
        .case-stat {
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }
        
        .case-stat strong {
            color: #111827;
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            background: white;
            border: 2px dashed #e5e7eb;
            border-radius: 8px;
        }
        
        .empty-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        
        .empty-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .empty-text {
            color: #6b7280;
            margin-bottom: 1.5rem;
        }
        
        /* PAGE 2: CASE DETAIL */
        .case-detail {
            display: none;
        }
        
        .case-detail.active {
            display: block;
        }
        
        .back-link {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            color: #6366f1;
            text-decoration: none;
            font-size: 0.875rem;
            margin-bottom: 1.5rem;
        }
        
        .back-link:hover {
            text-decoration: underline;
        }
        
        .detail-header {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 1.5rem;
        }
        
        .detail-title {
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .detail-meta {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-top: 1.5rem;
        }
        
        .meta-item {
            display: flex;
            flex-direction: column;
        }
        
        .meta-label {
            font-size: 0.75rem;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .meta-value {
            font-size: 1rem;
            font-weight: 600;
            color: #111827;
            margin-top: 0.25rem;
        }
        
        .detail-section {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        
        .section-title {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #111827;
        }
        
        .section-empty {
            color: #9ca3af;
            font-size: 0.875rem;
            font-style: italic;
        }
        
        /* Offers List */
        .offers-list {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        
        .offer-item {
            padding: 1rem;
            background: #f9fafb;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .offer-vendor {
            font-weight: 500;
            color: #111827;
        }
        
        .offer-price {
            font-size: 1.25rem;
            font-weight: 700;
            color: #6366f1;
        }
        
        .offer-details {
            display: flex;
            gap: 1rem;
            margin-top: 0.5rem;
            font-size: 0.875rem;
            color: #6b7280;
        }
        
        /* Emails List */
        .emails-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        
        .email-item {
            padding: 1rem;
            background: #f9fafb;
            border-radius: 6px;
            border-left: 3px solid #6366f1;
        }
        
        .email-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
        }
        
        .email-from {
            font-weight: 500;
            color: #111827;
            font-size: 0.875rem;
        }
        
        .email-time {
            font-size: 0.75rem;
            color: #9ca3af;
        }
        
        .email-subject {
            font-size: 0.875rem;
            color: #4b5563;
        }
        
        /* CHAT INTERFACE */
        .chat-modal {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 1000;
        }
        
        .chat-modal.active {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 1rem;
        }
        
        .chat-container {
            background: white;
            border-radius: 12px;
            width: 100%;
            max-width: 500px;
            height: 600px;
            max-height: 90vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .chat-header {
            padding: 1.25rem;
            border-bottom: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .chat-title {
            font-weight: 600;
            color: #111827;
        }
        
        .chat-close {
            background: none;
            border: none;
            font-size: 1.5rem;
            color: #9ca3af;
            cursor: pointer;
            line-height: 1;
        }
        
        .chat-close:hover {
            color: #111827;
        }
        
        .chat-messages {
            flex: 1;
            padding: 1.5rem;
            overflow-y: auto;
            background: #f9fafb;
        }
        
        .message {
            margin-bottom: 1rem;
        }
        
        .message-ai {
            text-align: left;
        }
        
        .message-user {
            text-align: right;
        }
        
        .message-bubble {
            display: inline-block;
            max-width: 80%;
            padding: 0.75rem 1rem;
            border-radius: 12px;
            font-size: 0.875rem;
        }
        
        .message-ai .message-bubble {
            background: white;
            color: #111827;
        }
        
        .message-user .message-bubble {
            background: #6366f1;
            color: white;
        }
        
        .chat-input-container {
            padding: 1rem;
            border-top: 1px solid #e5e7eb;
            display: flex;
            gap: 0.75rem;
        }
        
        .chat-input {
            flex: 1;
            padding: 0.625rem 1rem;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-size: 0.875rem;
            outline: none;
        }
        
        .chat-input:focus {
            border-color: #6366f1;
        }
        
        .chat-send {
            padding: 0.625rem 1.25rem;
            background: #6366f1;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
        }
        
        .chat-send:hover {
            background: #4f46e5;
        }
        
        /* Floating Action Button */
        .fab {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            width: 56px;
            height: 56px;
            background: #6366f1;
            color: white;
            border: none;
            border-radius: 50%;
            font-size: 1.5rem;
            cursor: pointer;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .fab:hover {
            background: #4f46e5;
            transform: scale(1.05);
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .cases-grid {
                grid-template-columns: 1fr;
            }
            
            .detail-meta {
                grid-template-columns: 1fr;
            }
            
            .chat-container {
                height: 100%;
                max-height: 100%;
                border-radius: 0;
            }
        }
    </style>
</head>
<body>
    <!-- Simple Header (Always Visible) -->
    <header class="header">
        <div class="logo">DGRO</div>
        <button class="new-case-btn" onclick="openChat()">+ New Case</button>
    </header>
    
    <!-- Main Container -->
    <div class="container">
        <!-- PAGE 1: Cases List View -->
        <div class="cases-list" id="casesPage">
            <h1 class="page-title">Your Cases</h1>
            
            <!-- Cases Grid -->
            <div class="cases-grid">
                <!-- Active Case 1 -->
                <div class="case-card" onclick="showCaseDetail()">
                    <span class="case-status status-active">Active</span>
                    <h3 class="case-title">Custom E-commerce Platform</h3>
                    <div class="case-info">
                        <span>📍 San Francisco, CA</span>
                        <span>💰 $25,000 - $35,000</span>
                        <span>⏱️ 3-4 months</span>
                    </div>
                    <div class="case-footer">
                        <span class="case-stat"><strong>5</strong> offers</span>
                        <span class="case-stat"><strong>8</strong> vendors</span>
                    </div>
                </div>
                
                <!-- Active Case 2 -->
                <div class="case-card" onclick="showCaseDetail()">
                    <span class="case-status status-active">Active</span>
                    <h3 class="case-title">Mobile App UI/UX Redesign</h3>
                    <div class="case-info">
                        <span>📍 Remote</span>
                        <span>💰 $8,000 - $12,000</span>
                        <span>⏱️ 6-8 weeks</span>
                    </div>
                    <div class="case-footer">
                        <span class="case-stat"><strong>3</strong> offers</span>
                        <span class="case-stat"><strong>12</strong> vendors</span>
                    </div>
                </div>
                
                <!-- Complete Case -->
                <div class="case-card" onclick="showCaseDetail()">
                    <span class="case-status status-complete">Complete</span>
                    <h3 class="case-title">Cloud Migration Services</h3>
                    <div class="case-info">
                        <span>📍 New York, NY</span>
                        <span>💰 $50,000 - $75,000</span>
                        <span>⏱️ 6 months</span>
                    </div>
                    <div class="case-footer">
                        <span class="case-stat"><strong>7</strong> offers</span>
                        <span class="case-stat"><strong>15</strong> vendors</span>
                    </div>
                </div>
            </div>
            
            <!-- Empty State (Hidden by default) -->
            <!--
            <div class="empty-state">
                <div class="empty-icon">📦</div>
                <h2 class="empty-title">No cases yet</h2>
                <p class="empty-text">Create your first case to start finding vendors</p>
                <button class="new-case-btn" onclick="openChat()">+ Create First Case</button>
            </div>
            -->
        </div>
        
        <!-- PAGE 2: Case Detail View -->
        <div class="case-detail" id="detailPage">
            <a href="#" class="back-link" onclick="showCasesList()">← Back to Cases</a>
            
            <!-- Case Header -->
            <div class="detail-header">
                <span class="case-status status-active">Active</span>
                <h1 class="detail-title">Custom E-commerce Platform Development</h1>
                <div class="detail-meta">
                    <div class="meta-item">
                        <span class="meta-label">Location</span>
                        <span class="meta-value">San Francisco, CA</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Budget</span>
                        <span class="meta-value">$25,000 - $35,000</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Timeline</span>
                        <span class="meta-value">3-4 months</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Created</span>
                        <span class="meta-value">Nov 15, 2024</span>
                    </div>
                </div>
            </div>
            
            <!-- Requirements -->
            <div class="detail-section">
                <h2 class="section-title">Requirements</h2>
                <p style="color: #4b5563; line-height: 1.6;">
                    React-based frontend, Node.js backend, PostgreSQL database, 
                    Stripe payment integration, AWS hosting with auto-scaling, 
                    CI/CD pipeline, admin dashboard, customer portal with order tracking, 
                    inventory management system.
                </p>
            </div>
            
            <!-- Offers -->
            <div class="detail-section">
                <h2 class="section-title">Current Offers (5)</h2>
                <div class="offers-list">
                    <div class="offer-item">
                        <div>
                            <div class="offer-vendor">TechCraft Solutions</div>
                            <div class="offer-details">
                                <span>📅 12 weeks</span>
                                <span>✅ Best offer</span>
                            </div>
                        </div>
                        <div class="offer-price">$27,500</div>
                    </div>
                    
                    <div class="offer-item">
                        <div>
                            <div class="offer-vendor">Digital Innovations Inc.</div>
                            <div class="offer-details">
                                <span>📅 14 weeks</span>
                            </div>
                        </div>
                        <div class="offer-price">$29,000</div>
                    </div>
                    
                    <div class="offer-item">
                        <div>
                            <div class="offer-vendor">WebMasters Pro</div>
                            <div class="offer-details">
                                <span>📅 16 weeks</span>
                            </div>
                        </div>
                        <div class="offer-price">$32,000</div>
                    </div>
                </div>
            </div>
            
            <!-- Recent Emails -->
            <div class="detail-section">
                <h2 class="section-title">Recent Communications</h2>
                <div class="emails-list">
                    <div class="email-item">
                        <div class="email-header">
                            <span class="email-from">TechCraft Solutions</span>
                            <span class="email-time">2 hours ago</span>
                        </div>
                        <div class="email-subject">Re: E-commerce Platform Development Proposal</div>
                    </div>
                    
                    <div class="email-item">
                        <div class="email-header">
                            <span class="email-from">Digital Innovations Inc.</span>
                            <span class="email-time">5 hours ago</span>
                        </div>
                        <div class="email-subject">Updated Quote - Special Pricing Available</div>
                    </div>
                    
                    <div class="email-item">
                        <div class="email-header">
                            <span class="email-from">WebMasters Pro</span>
                            <span class="email-time">Yesterday</span>
                        </div>
                        <div class="email-subject">Initial Proposal and Timeline</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Floating Action Button (Mobile) -->
    <button class="fab" onclick="openChat()">+</button>
    
    <!-- Chat Modal -->
    <div class="chat-modal" id="chatModal">
        <div class="chat-container">
            <div class="chat-header">
                <span class="chat-title">🤖 Discovery Consultant</span>
                <button class="chat-close" onclick="closeChat()">×</button>
            </div>
            
            <div class="chat-messages">
                <div class="message message-ai">
                    <div class="message-bubble">
                        Hi! I'm your Discovery Consultant. Tell me what you're looking for and I'll help you find the best vendors and negotiate great deals. What project do you need help with?
                    </div>
                </div>
                
                <div class="message message-user">
                    <div class="message-bubble">
                        I need a custom e-commerce platform built
                    </div>
                </div>
                
                <div class="message message-ai">
                    <div class="message-bubble">
                        Great! I'll help you find vendors for your e-commerce platform. Let me ask a few questions:
                        <br><br>
                        1. What's your budget range?<br>
                        2. When do you need it completed?<br>
                        3. What's your location (or do you prefer remote)?<br>
                        4. Any specific technologies required?
                    </div>
                </div>
            </div>
            
            <div class="chat-input-container">
                <input type="text" class="chat-input" placeholder="Type your message...">
                <button class="chat-send">Send</button>
            </div>
        </div>
    </div>
    
    <script>
        // Simple page navigation
        function showCaseDetail() {
            document.getElementById('casesPage').style.display = 'none';
            document.getElementById('detailPage').style.display = 'block';
            window.scrollTo(0, 0);
        }
        
        function showCasesList() {
            document.getElementById('detailPage').style.display = 'none';
            document.getElementById('casesPage').style.display = 'block';
        }
        
        // Chat modal
        function openChat() {
            document.getElementById('chatModal').classList.add('active');
        }
        
        function closeChat() {
            document.getElementById('chatModal').classList.remove('active');
        }
        
        // Handle Enter key in chat
        document.querySelector('.chat-input')?.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                // Send message logic here
                console.log('Send message:', this.value);
                this.value = '';
            }
        });
    </script>
</body>
</html>