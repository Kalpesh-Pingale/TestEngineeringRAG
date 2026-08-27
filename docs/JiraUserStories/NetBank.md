NetBank - Detailed User Stories & Acceptance Criteria
1. Customer Registration
User Story: As a new customer, I want to register for online banking using my account number and personal details so that I can access my accounts digitally.
Acceptance Criteria:
Registration form includes account number, date of birth, registered mobile, email.
Identity verified via OTP sent to registered mobile.
Duplicate registration → error message.
Password must meet complexity rules (min length, upper/lower case, number, special char).
Successful registration → activation email and redirect to login page.
2. Customer Login
User Story: As a registered customer, I want to log in securely with my credentials and a second factor so that only I can access my accounts.
Acceptance Criteria:
User enters username/customer ID and password.
Second factor (OTP or authenticator) required after password.
Successful login redirects to account dashboard.
Invalid credentials → generic error message (no account enumeration).
Account locked after 5 failed attempts with unlock via support/OTP.
3. View Account Balance and Statement
User Story: As a customer, I want to view my account balance and transaction history so that I can track my money.
Acceptance Criteria:
Dashboard shows all linked accounts with current and available balance.
Statement lists date, description, debit/credit, running balance.
Statement filterable by date range and transaction type.
Statement downloadable as PDF and CSV.
No transactions in range → "No transactions found."
4. Fund Transfer - Own Accounts
User Story: As a customer, I want to transfer money between my own accounts so that I can manage my funds instantly.
Acceptance Criteria:
User selects source and destination account from linked accounts.
Amount validated against available balance.
Transfer processed instantly and reflected in both balances.
Confirmation screen shows reference number.
Insufficient funds → error message, no transfer.
5. Fund Transfer - Third Party (Payee)
User Story: As a customer, I want to add a payee and transfer money to them so that I can pay other people and businesses.
Acceptance Criteria:
Add payee with name, account number, IFSC/routing code, nickname.
New payee activation requires OTP and a cooling period.
Transfer requires amount, payee selection, and OTP authorization.
Daily transfer limit enforced; breach → error message.
Successful transfer → reference number and email/SMS notification.
6. Bill Payment
User Story: As a customer, I want to pay utility bills from my account so that I can settle bills without visiting the biller.
Acceptance Criteria:
User selects biller category and biller, enters consumer/reference number.
Outstanding amount fetched where biller supports it.
Payment validated against available balance and limits.
Successful payment → receipt with reference number.
Failed payment → amount not debited or auto-reversed with notification.
7. Recurring Payments and Standing Instructions
User Story: As a customer, I want to schedule recurring transfers so that regular payments happen automatically.
Acceptance Criteria:
User sets payee, amount, frequency, start date, and end condition.
Standing instruction listed under scheduled payments.
Execution on due date if sufficient funds; else retry and notify.
User can pause, edit, or cancel an instruction before the next run.
Each execution generates a transaction record and notification.
8. Card Management
User Story: As a customer, I want to manage my debit and credit cards so that I can control how they are used.
Acceptance Criteria:
Card list shows masked number, type, status, expiry.
User can freeze/unfreeze a card instantly.
User can set per-channel limits (POS, online, ATM, international).
User can request a replacement card with delivery tracking.
Sensitive actions require OTP authorization.
9. Profile and Security Settings
User Story: As a customer, I want to update my profile and security settings so that my contact details and access stay current and safe.
Acceptance Criteria:
Profile page shows name, email, phone, mailing address.
Email or phone change requires OTP verification of the new value.
Password change requires current password and enforces complexity rules.
User can view active sessions and log out other devices.
User can enable/disable login alerts and set transaction alert thresholds.
10. Logout
User Story: As a customer, I want to log out and be logged out automatically when idle so that my accounts stay secure.
Acceptance Criteria:
Logout option available on every page.
Clicking logout ends the session and clears session data.
Session auto-expires after a defined idle timeout with a warning prompt.
After logout, using the back button does not expose account data.
Re-access requires full login with second factor.
📄 Text File Structure
Each story can be saved as a .txt file with this format:
Code
User Story:
As a customer, I want to transfer money between my own accounts so that I can manage my funds instantly.

Acceptance Criteria:
- User selects source and destination account from linked accounts.
- Amount validated against available balance.
- Transfer processed instantly and reflected in both balances.
- Confirmation screen shows reference number.
- Insufficient funds → error message, no transfer.
