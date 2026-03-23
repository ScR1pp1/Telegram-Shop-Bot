import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { http } from "../api/http";
import { setBackButtonHandler, removeBackButtonHandler } from "../telegram/tma";

type Order = {
  id: number;
  full_name: string;
  address: string;
  phone: string;
  total: string;
  status: string;
  created_at: string;
  items: { product: { name: string }; quantity: number; price: string }[];
};

export function OrderSuccessPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();

  const { data: order, isLoading, isError } = useQuery({
    queryKey: ["order", orderId],
    queryFn: async () => (await http.get<Order>(`/orders/${orderId}/`)).data,
    enabled: !!orderId,
  });

  useEffect(() => {
    setBackButtonHandler(() => navigate("/catalog"));
    return () => removeBackButtonHandler();
  }, [navigate]);

  if (isLoading) return <div className="loading">Загрузка...</div>;
  if (isError || !order) return <div className="error">Ошибка загрузки заказа</div>;

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="container">
      <h2>✅ Заказ оформлен!</h2>
      <div className="order-success-card">
        <div className="order-success-header">
          <span className="order-id">Заказ #{order.id}</span>
          <span className="order-status">{order.status === "pending_payment" ? "⏳ Ожидает оплаты" : order.status}</span>
        </div>
        <div className="order-details">
          <p><strong>Дата:</strong> {formatDate(order.created_at)}</p>
          <p><strong>Получатель:</strong> {order.full_name}</p>
          <p><strong>Телефон:</strong> {order.phone}</p>
          <p><strong>Адрес:</strong> {order.address}</p>
          <div className="order-items">
            <strong>Товары:</strong>
            <ul>
              {order.items.map((item, idx) => (
                <li key={idx}>
                  {item.product.name} × {item.quantity} = {Number(item.price) * item.quantity} ₽
                </li>
              ))}
            </ul>
          </div>
          <p className="order-total"><strong>Итого:</strong> {order.total} ₽</p>
        </div>
        <button
          onClick={() => navigate("/catalog")}
          className="button-primary"
          style={{ marginTop: 20, width: "100%" }}
        >
          🛍️ Продолжить покупки
        </button>
      </div>
    </div>
  );
}