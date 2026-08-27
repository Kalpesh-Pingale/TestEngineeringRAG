ShopCart - Detailed User Stories & Acceptance Criteria
1. User Registration
User Story: As a new user, I want to register with my email and password so that I can create an account and shop online.
Acceptance Criteria:
Registration form includes name, email, password, confirm password.
Password must meet complexity rules (min length, special char).
Duplicate email → error message.
Successful registration → confirmation email sent.
User redirected to login page after registration.
2. User Login
User Story: As a registered user, I want to log in with my credentials so that I can access my account and place orders.
Acceptance Criteria:
User enters valid email/username and password.
Credentials validated against stored records.
Successful login redirects to homepage/dashboard.
Invalid credentials → error message.
“Forgot password” option available.
3. Search Product
User Story: As a shopper, I want to search for products by name or category so that I can quickly find items I want to buy.
Acceptance Criteria:
Search bar visible on all pages.
Keyword search returns relevant products.
Results show product name, price, thumbnail.
No results → “No products found.”
Filters available (category, price range, rating).
4. Product Details
User Story: As a shopper, I want to view detailed product information so that I can make an informed purchase decision.
Acceptance Criteria:
Product detail page shows name, description, price, stock status, images.
User can select size/color variants if applicable.
Reviews and ratings displayed.
“Add to Cart” button available.
5. Add to Cart
User Story: As a shopper, I want to add products to my cart so that I can purchase multiple items in one order.
Acceptance Criteria:
“Add to Cart” button adds product to cart.
Cart icon updates with item count.
Cart page shows product name, price, quantity.
User can update quantity or remove items.
Cart persists during session until checkout.
6. Checkout
User Story: As a shopper, I want to checkout my cart so that I can complete my purchase securely.
Acceptance Criteria:
Checkout page displays cart summary (items, total price).
User enters shipping details and payment info.
Payment validated before confirming order.
Successful order → confirmation page + email receipt.
Failed payment → error message with retry option.
7. Order History
User Story: As a registered user, I want to view my past orders so that I can track purchases and reorder items.
Acceptance Criteria:
Order history page lists all past orders.
Each order shows date, items, total, status.
User can click an order to view details.
Option to reorder items available.
8. Wishlist
User Story: As a shopper, I want to save products to a wishlist so that I can purchase them later.
Acceptance Criteria:
“Add to Wishlist” button available on product pages.
Wishlist page shows saved products.
User can move items from wishlist to cart.
User can remove items from wishlist.
9. Profile Management
User Story: As a registered user, I want to update my profile details so that my account information stays current.
Acceptance Criteria:
Profile page shows name, email, phone, address.
User can edit and save changes.
Email change requires verification.
Password change requires old password confirmation.
10. Logout
User Story: As a user, I want to log out so that my account remains secure when I leave the site.
Acceptance Criteria:
Logout option available on all pages.
Clicking logout ends session and redirects to homepage/login.
Cart and wishlist persist for logged‑in users after re‑login.
📄 Text File Structure
Each story can be saved as a .txt file with this format:
Code
User Story:
As a shopper, I want to search for products by name or category so that I can quickly find items I want to buy.

Acceptance Criteria:
- Search bar visible on all pages.
- Keyword search returns relevant products.
- Results show product name, price, thumbnail.
- No results → “No products found.”
- Filters available (category, price range, rating).


