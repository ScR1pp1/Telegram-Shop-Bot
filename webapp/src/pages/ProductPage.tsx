import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/http";

type ProductImage = { id: number; image: string; order: number };
type Product = {
  id: number;
  name: string;
  description: string;
  price: string;
  images: ProductImage[];
};

export function ProductPage() {
  const { id } = useParams<{ id: string }>();
  console.log("ProductPage id:", id);
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["product", id],
    queryFn: async () => (await http.get<Product>(`/products/${id}/`)).data,
  });

  const addToCart = async (productId: number) => {
    try {
      await http.post("/cart/", { product_id: productId, quantity: 1 });
      qc.invalidateQueries({ queryKey: ["cart"] });
      alert("Товар добавлен в корзину");
    } catch (err) {
      console.error(err);
      alert("Не удалось добавить товар");
    }
  };

  const addToWishlist = async (productId: number) => {
    try {
      await http.post("/wishlist/", { product_id: productId });
      qc.invalidateQueries({ queryKey: ["wishlist"] });
      alert("⭐ Добавлено в избранное");
    } catch (err) {
      console.error(err);
      alert("Не удалось добавить в избранное");
    }
  };

  if (isLoading) return <div style={{ padding: 16 }}>Загрузка...</div>;
  if (error || !data) return <div style={{ padding: 16 }}>Товар не найден</div>;

  return (
    <div style={{ padding: 16 }}>
      <button onClick={() => navigate("/catalog")} style={{ marginBottom: 16 }}>← Назад</button>
      {data.images && data.images.length > 0 && (
        <img
          src={data.images[0].image}
          alt={data.name}
          style={{ width: "100%", borderRadius: 16, marginBottom: 16 }}
        />
      )}
      <h2 style={{ marginTop: 0 }}>{data.name}</h2>
      <p style={{ marginBottom: 16 }}>{data.description}</p>
      <div style={{ fontSize: 24, fontWeight: 700, marginBottom: 16 }}>{data.price} ₽</div>
      <div style={{ display: "flex", gap: 12 }}>
        <button
          onClick={() => addToCart(data.id)}
          style={{
            flex: 1,
            padding: 12,
            background: "var(--tma-button-color, #40a7e3)",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            fontSize: 16,
            cursor: "pointer",
          }}
        >
          В корзину
        </button>
        <button
        onClick={() => addToWishlist(data.id)}
        style={{
            flex: 1,
            padding: 12,
            background: "var(--tma-secondary-bg-color, #f0f0f0)",
            color: "var(--tma-text-color, #000)",
            border: "1px solid var(--tma-hint-color, #ccc)",
            borderRadius: 8,
            fontSize: 16,
            cursor: "pointer",
        }}
        >
        ⭐ В избранное
        </button>
      </div>
    </div>
  );
}