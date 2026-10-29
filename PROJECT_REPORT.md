# EC4307 Web Application Development — Mini Project Report

**Project:** NovaCart — E-Commerce Store  
**Student:** Bandara K.M.S.N  
**Registration Number:** EG/2023/5515  
**Date:** __________________

## 1. Introduction
NovaCart is a web-based e-commerce store prototype designed to demonstrate core online shopping workflows. Visitors can browse a product catalogue, search and filter products, inspect product details, add products to a cart and place a demo order. Store operators can manage products and inspect orders.

## 2. Objectives
- Build a responsive and easy-to-use shopping interface.
- Implement full CRUD operations for the product entity.
- Store product, order and order-item data persistently in a relational database.
- Validate user input and prevent invalid quantities and stock overselling in normal demo use.
- Demonstrate search, filtering, sorting and basic order processing.

## 3. Technologies
- **Python / Flask:** routing, request handling and server-side validation.
- **SQLite:** persistent relational database.
- **HTML/Jinja templates:** page structure and dynamic content.
- **CSS:** responsive layout and visual design.
- **Browser session:** temporary shopping-cart state.

## 4. Functional requirements
1. Display product listings and individual product details.
2. Search by product name, description or category; filter by category; sort by name or price.
3. Create, read, update and delete product records.
4. Add products to a cart and update quantities.
5. Collect customer name, email and delivery address for a demo order.
6. Save orders and order items; reduce product stock after successful order creation.
7. View order summaries and order details.

## 5. Database design
The database contains three tables. `products` stores product details and stock. `orders` stores customer and order totals. `order_items` stores a snapshot of each purchased product name, quantity and unit price. Each order item belongs to an order; its optional product reference is set to NULL if that product is later deleted. Primary keys uniquely identify records and foreign keys maintain referential integrity.

**ERD:** See the Mermaid ERD in `README.md` (Products → Order Items ← Orders).

## 6. Implementation and validation
Flask routes implement the storefront, product detail page, cart, checkout, product-management forms and order views. SQL statements use parameterized values. Server-side checks validate required product fields, non-negative price and stock, quantity availability, and basic email format. Order placement checks stock again before saving the order and decrementing inventory in a database transaction.

## 7. User interface and responsiveness
The interface uses a consistent navigation bar, product cards, search/filter controls, clear action buttons and feedback messages. CSS media queries adapt product grids, navigation, forms and detail pages for narrower screens. Product images are optional; a styled placeholder is shown when no image URL is provided.

## 8. Testing plan and results to record
Run the test checklist in `README.md`. Capture screenshots from the running application for: storefront, search/filter results, product details, add/edit product form, product list with edit/delete actions, cart, checkout success page, and order details. Fill in the table only after executing the tests.

| Test | Expected result | Actual result |
|---|---|---|
| Create valid product | Product saved and listed | To be completed |
| Invalid price / stock | Validation error shown | To be completed |
| Search/filter/sort | Matching sorted results | To be completed |
| Edit product | Updated values persist | To be completed |
| Delete product | Product removed | To be completed |
| Checkout within stock | Order saved; stock reduced | To be completed |
| Quantity above stock | Request rejected | To be completed |
| Mobile viewport | Layout adapts to screen | To be completed |

## 9. Limitations and future improvements
This prototype has no administrator login, real payment processing, automated email, CSRF protection or deployment hardening. Future work could add authenticated roles, product image upload, order status management, payment gateway integration, email notifications, automated unit/integration tests and cloud deployment with HTTPS.

## 10. Conclusion
NovaCart demonstrates the main e-commerce catalogue and order workflow while providing persistent database storage and full product CRUD operations. Before submission, the student should run the application, complete the test table with actual results, add genuine interface screenshots and ensure the final report stays within the maximum 10-page limit.
