import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/http";
import { useNavigate } from "react-router-dom";
import { setBackButtonHandler, removeBackButtonHandler } from "../telegram/tma";

type Product = { id: number; name: string; price: string };
type CartItem = { id: number; quantity: number; product: Product };

export function CartPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["cart"],
    queryFn: async () => (await http.get<CartItem[]>("/cart/")).data,
  });

  const items = data ?? [];
  const total = items.reduce((acc, it) => acc + Number(it.product.price) * it.quantity, 0);

  useEffect(() => {
    setBackButtonHandler(() => navigate("/catalog"));
    return () => {
      removeBackButtonHandler();
    };
  }, [navigate]);

  const updateQuantity = async (itemId: number, newQty: number) => {
    if (newQty < 1) return;
    await http.patch(`/cart/${itemId}/`, { quantity: newQty });
    qc.invalidateQueries({ queryKey: ["cart"] });
  };

  const clearCart = async () => {
    for (const item of items) await http.delete(`/cart/${item.id}/`);
    qc.invalidateQueries({ queryKey: ["cart"] });
  };

  const checkout = () => navigate("/checkout");

  if (isLoading) return <div className="loading">Загрузка корзины…</div>;
  if (isError) return <div className="error">Ошибка загрузки корзины</div>;

  return (
    <div className="container">
      <h2>🛒 Корзина</h2>
      {items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🛒</div>
          <p>Корзина пуста</p>
          <button onClick={() => navigate("/catalog")} className="button-primary">
            Перейти в каталог
          </button>
        </div>
      ) : (
        <>
          {items.map((item) => (
            <div key={item.id} className="cart-item">
              <div className="cart-item-info">
                <div className="cart-item-name">{item.product.name}</div>
                <div className="cart-item-price">
                  {item.product.price} ₽ × {item.quantity} = {Number(item.product.price) * item.quantity} ₽
                </div>
              </div>
              <div className="cart-item-actions">
                <div className="quantity-control">
                  <button
                    onClick={() => updateQuantity(item.id, item.quantity - 1)}
                    className="quantity-btn"
                  >
                    −
                  </button>
                  <span className="quantity-value">{item.quantity}</span>
                  <button
                    onClick={() => updateQuantity(item.id, item.quantity + 1)}
                    className="quantity-btn"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
          ))}
          <div className="cart-total">Итого: {total.toFixed(2)} ₽</div>
          <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
            <button onClick={clearCart} className="button-secondary" style={{ flex: 1 }}>
              Очистить
            </button>
            <button onClick={checkout} className="button-primary" style={{ flex: 1 }}>
              Оформить заказ
            </button>
          </div>
          <button
            onClick={() => navigate("/catalog")}
            className="button-secondary"
            style={{ marginTop: 16, width: "100%" }}
          >
            ← Вернуться в каталог
          </button>
        </>
      )}
    </div>
  );
}