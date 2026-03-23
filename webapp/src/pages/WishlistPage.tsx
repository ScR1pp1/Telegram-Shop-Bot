import { useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/http";
import { useNavigate } from "react-router-dom";

type Product = { id: number; name: string; price: string };
type WishlistItem = { id: number; product: Product; created_at: string };

export function WishlistPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["wishlist"],
    queryFn: async () => (await http.get<WishlistItem[]>("/wishlist/")).data,
  });

  const items = data ?? [];

  const addToCart = async (productId: number) => {
    try {
      await http.post("/cart/", { product_id: productId, quantity: 1 });
      qc.invalidateQueries({ queryKey: ["cart"] });
      alert("✅ Товар добавлен в корзину");
    } catch (err) {
      console.error(err);
      alert("Не удалось добавить товар");
    }
  };

  const removeFromWishlist = async (itemId: number) => {
    try {
      await http.delete(`/wishlist/${itemId}/`);
      qc.invalidateQueries({ queryKey: ["wishlist"] });
      alert("❌ Удалено из избранного");
    } catch (err) {
      console.error(err);
      alert("Не удалось удалить");
    }
  };

  if (isLoading) return <div style={{ padding: 16 }}>Загрузка избранного…</div>;
  if (isError) return <div style={{ padding: 16 }}>Ошибка загрузки избранного</div>;

  return (
    <div style={{ padding: 16 }}>
      <h2>⭐ Избранное</h2>
      {items.length === 0 ? (
        <p>У вас пока нет избранных товаров</p>
      ) : (
        items.map((item) => (
          <div
            key={item.id}
            style={{
              border: "1px solid var(--tma-hint-color, #e0e0e0)",
              borderRadius: 16,
              padding: 12,
              marginBottom: 12,
              background: "var(--tma-bg, #fff)",
              color: "var(--tma-text, #000)",
            }}
          >
            <div style={{ fontWeight: 700 }}>{item.product.name}</div>
            <div style={{ opacity: 0.8 }}>{item.product.price} ₽</div>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button
                onClick={() => addToCart(item.product.id)}
                style={{
                  flex: 1,
                  padding: "8px",
                  background: "var(--tma-button-color, #40a7e3)",
                  color: "var(--tma-button-text-color, #fff)",
                  border: "none",
                  borderRadius: 8,
                  cursor: "pointer",
                }}
              >
                🛒 В корзину
              </button>
              <button
                onClick={() => removeFromWishlist(item.id)}
                style={{
                  flex: 1,
                  padding: "8px",
                  background: "var(--tma-secondary-bg-color, #f0f0f0)",
                  color: "var(--tma-text-color, #000)",
                  border: "1px solid var(--tma-hint-color, #ccc)",
                  borderRadius: 8,
                  cursor: "pointer",
                }}
              >
                ❌ Удалить
              </button>
            </div>
          </div>
        ))
      )}
      <button
        onClick={() => navigate("/catalog")}
        className="button-secondary"
        style={{ marginTop: 16, width: "100%" }}
      >
        ← Вернуться в каталог
      </button>
    </div>
  );
}