import { useMemo, useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/http";
import { useNavigate } from "react-router-dom";
import { setBackButtonHandler, removeBackButtonHandler } from "../telegram/tma";

type ProductImage = { id: number; image: string; order: number };
type Product = { id: number; name: string; description: string; price: string; images: ProductImage[] };
type Category = { id: number; name: string; parent: number | null; children?: Category[]; has_products: boolean };

function useDebounced(v: string, ms: number) {
  const [d, setD] = useState(v);
  useEffect(() => {
    const t = setTimeout(() => setD(v), ms);
    return () => clearTimeout(t);
  }, [v, ms]);
  return d;
}

export function CatalogPage() {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<number | null>(null);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const debounced = useDebounced(search, 300);

  const { data: categories, isLoading: categoriesLoading } = useQuery({
    queryKey: ["categories"],
    queryFn: async () => (await http.get<Category[]>("/categories/")).data,
  });

  const fetchWithRetry = async <T,>(url: string, params?: any): Promise<T> => {
    let lastError;
    for (let i = 0; i < 3; i++) {
      try {
        const response = await http.get<T>(url, { params });
        if (typeof response.data === 'string' && response.data.includes('<!DOCTYPE')) {
          throw new Error('Received HTML instead of JSON');
        }
        return response.data;
      } catch (error) {
        lastError = error;
        await new Promise(resolve => setTimeout(resolve, (i + 1) * 1000));
      }
    }
    throw lastError;
  };

  const productsQ = useQuery({
    queryKey: ["products", debounced, selectedCategory],
    queryFn: () =>
      fetchWithRetry<Product[]>("/products/", {
        search: debounced || undefined,
        category: selectedCategory ?? undefined,
      }),
    retry: 3,
    retryDelay: 1000,
  });

  useEffect(() => {
    if (productsQ.isError) {
      const timer = setTimeout(() => window.location.reload(), 5000);
      return () => clearTimeout(timer);
    }
  }, [productsQ.isError]);

  useEffect(() => {
    removeBackButtonHandler();
    return () => removeBackButtonHandler();
  }, []);

  const addToCart = async (productId: number) => {
    for (let i = 0; i < 3; i++) {
      try {
        await http.post("/cart/", { product_id: productId, quantity: 1 });
        qc.invalidateQueries({ queryKey: ["cart"] });
        alert("Товар добавлен в корзину");
        return;
      } catch (error) {
        if (i === 2) alert("Не удалось добавить товар. Попробуйте позже.");
        else await new Promise(resolve => setTimeout(resolve, (i + 1) * 500));
      }
    }
  };

  const addToWishlist = async (productId: number) => {
    try {
      await http.post("/wishlist/", { product_id: productId });
      alert("⭐ Добавлено в избранное");
      qc.invalidateQueries({ queryKey: ["wishlist"] });
    } catch (error) {
      console.error(error);
      alert("Не удалось добавить в избранное");
    }
  };

  const renderProducts = () => {
    if (productsQ.isLoading) return <div className="loading">Загрузка товаров...</div>;
    if (productsQ.isError) return <div className="error">Ошибка загрузки товаров</div>;

    const products = productsQ.data;
    if (!products || !Array.isArray(products) || products.length === 0)
      return <div className="empty-state">Нет товаров</div>;

    return (
      <div className="product-grid">
        {products.map((p) => (
          <div
            key={p.id}
            className="product-card"
            onClick={() => navigate(`/product/${p.id}`)}
          >
            {p.images && p.images.length > 0 && (
              <img
                src={p.images[0].image}
                alt={p.name}
                className="product-image"
              />
            )}
            <div className="product-name">{p.name}</div>
            <div className="product-description">{p.description?.slice(0, 60)}...</div>
            <div className="product-price">{p.price} ₽</div>
            <div className="product-actions">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  addToWishlist(p.id);
                }}
                className="button-secondary"
              >
                ⭐
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  addToCart(p.id);
                }}
                className="button-primary"
              >
                В корзину
              </button>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderCategories = () => {
    if (categoriesLoading) return <div className="loading">Загрузка категорий...</div>;
    if (!categories || categories.length === 0) return null;
  
    const flatCategories = (cats: Category[], level = 0): Category[] => {
      let result: Category[] = [];
      for (const cat of cats) {
        if (cat.has_products) {
          result.push({ ...cat, level } as any);
        }
        if (cat.children) {
          result.push(...flatCategories(cat.children, level + 1));
        }
      }
      return result;
    };
  
    const allCats = flatCategories(categories);
    return (
      <div className="categories">
        <button
          key="all"
          className={`category-chip ${selectedCategory === null ? 'active' : ''}`}
          onClick={() => setSelectedCategory(null)}
        >
          Все
        </button>
        {allCats.map(cat => (
          <button
            key={cat.id}
            className={`category-chip ${selectedCategory === cat.id ? 'active' : ''}`}
            style={{ marginLeft: (cat as any).level * 16 }}
            onClick={() => setSelectedCategory(cat.id)}
          >
            {cat.name}
          </button>
        ))}
      </div>
    );
  };

  return (
    <div className="container">
      <div className="catalog-header">
        <h2>Каталог</h2>
        <div className="header-buttons">
          <button onClick={() => navigate("/wishlist")} className="icon-button">⭐</button>
          <button onClick={() => navigate("/cart")} className="button-primary">🛒 Корзина</button>
        </div>
      </div>

      <div className="search-section">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Поиск по названию"
          className="search-input"
        />
        <button onClick={() => setSearch("")} className="button-secondary">Сбросить</button>
      </div>

      {renderCategories()}

      {renderProducts()}
    </div>
  );
}