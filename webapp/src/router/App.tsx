import { Navigate, Route, Routes } from "react-router-dom";
import { CatalogPage } from "../pages/CatalogPage";
import { CartPage } from "../pages/CartPage";
import { CheckoutPage } from "../pages/CheckoutPage";
import { OrderSuccessPage } from "../pages/OrderSuccessPage";
import { WishlistPage } from "../pages/WishlistPage";
import { ProductPage } from "../pages/ProductPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/catalog" replace />} />
      <Route path="/catalog" element={<CatalogPage />} />
      <Route path="/cart" element={<CartPage />} />
      <Route path="/checkout" element={<CheckoutPage />} />
      <Route path="/success/:orderId" element={<OrderSuccessPage />} />
      <Route path="/wishlist" element={<WishlistPage />} />
      <Route path="/product/:id" element={<ProductPage />} />
    </Routes>
  );
}