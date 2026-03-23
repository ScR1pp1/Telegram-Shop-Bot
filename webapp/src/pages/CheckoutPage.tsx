import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { http } from "../api/http";
import { getTelegramWebApp, setBackButtonHandler, removeBackButtonHandler } from "../telegram/tma";
import { useQueryClient } from "@tanstack/react-query";

export function CheckoutPage() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");

  const valid = useMemo(() => 
    fullName.trim().length > 0 && 
    address.trim().length > 0 && 
    phone.trim().length > 0, 
    [fullName, address, phone]
  );

  useEffect(() => {
    const tma = getTelegramWebApp();
    if (!tma) return;
    
    tma.MainButton.setText("Оформить заказ");
    tma.MainButton.setParams({ is_active: valid, is_visible: true });
    
    const onClick = async () => {
      try {
        const resp = await http.post("/orders/", { full_name: fullName, address, phone });
        await qc.invalidateQueries({ queryKey: ["cart"] });
        nav(`/success/${resp.data.id}`);
      } catch (error) {
        console.error("Ошибка при создании заказа:", error);
        alert("Не удалось создать заказ. Попробуйте позже.");
      }
    };
    
    tma.MainButton.onClick(onClick);
    
    setBackButtonHandler(() => nav("/cart"));
    
    return () => {
      tma.MainButton.offClick(onClick);
      tma.MainButton.hide();
      removeBackButtonHandler();
    };
  }, [valid, fullName, address, phone, nav, qc]);

  return (
    <div className="container">
      <h2>Оформление заказа</h2>
      <div className="checkout-form">
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="ФИО"
          className="checkout-input"
        />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Телефон"
          className="checkout-input"
          type="tel"
        />
        <textarea
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="Адрес доставки"
          rows={3}
          className="checkout-textarea"
        />
        <button
          disabled={!valid}
          onClick={async () => {
            try {
              const resp = await http.post("/orders/", { full_name: fullName, address, phone });
              await qc.invalidateQueries({ queryKey: ["cart"] });
              nav(`/success/${resp.data.id}`);
            } catch (error) {
              alert("Ошибка при создании заказа");
            }
          }}
          className="button-primary"
        >
          Создать заказ
        </button>
      </div>
    </div>
  );
}