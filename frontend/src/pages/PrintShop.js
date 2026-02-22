import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import {
  ArrowLeft, ShoppingCart, Plus, Minus, Trash2, Printer, Check
} from "lucide-react";
import {
  getShareFiles, getSharePrintSizes, createPrintOrder, previewUrl
} from "@/lib/api";

export default function PrintShop() {
  const { token } = useParams();
  const navigate = useNavigate();
  const cartRef = React.useRef(null);
  
  const MINIMUM_ORDER = 15.00; // Minimum order value in GBP
  
  const [galleryName, setGalleryName] = useState("");
  const [galleryId, setGalleryId] = useState(null);
  const [files, setFiles] = useState([]);
  const [printSizes, setPrintSizes] = useState([]);
  const [shippingCost, setShippingCost] = useState(2.50);
  const [loading, setLoading] = useState(true);
  
  const [cart, setCart] = useState([]); // [{file_id, filename, size_id, size_name, finish, quantity, unit_price}]
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [orderComplete, setOrderComplete] = useState(null);

  const loadData = useCallback(async () => {
    try {
      const [filesRes, sizesRes] = await Promise.all([
        getShareFiles(token),
        getSharePrintSizes(token)
      ]);
      
      setGalleryName(filesRes.data.gallery_name);
      setGalleryId(filesRes.data.gallery_id);
      
      // Flatten all photos from all subfolders
      const allPhotos = [];
      filesRes.data.subfolders.forEach(sf => {
        sf.files.filter(f => f.file_type === 'photo').forEach(f => {
          allPhotos.push({ ...f, subfolder: sf.name });
        });
      });
      setFiles(allPhotos);
      
      setPrintSizes(sizesRes.data.sizes);
      setShippingCost(sizesRes.data.shipping_cost);
    } catch (err) {
      toast.error("Failed to load print shop");
      navigate(`/s/${token}/view`);
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

  useEffect(() => {
    const jwt = localStorage.getItem("share_token");
    const urlToken = localStorage.getItem("share_url_token");
    if (!jwt || urlToken !== token) {
      navigate(`/s/${token}`);
      return;
    }
    loadData();
  }, [token, navigate, loadData]);

  const addToCart = (file, sizeId, finish) => {
    const size = printSizes.find(s => s.id === sizeId);
    if (!size) return;
    
    const price = size.prices[finish];
    const existing = cart.find(c => c.file_id === file.id && c.size_id === sizeId && c.finish === finish);
    
    if (existing) {
      setCart(cart.map(c => 
        c.file_id === file.id && c.size_id === sizeId && c.finish === finish
          ? { ...c, quantity: c.quantity + 1 }
          : c
      ));
    } else {
      setCart([...cart, {
        file_id: file.id,
        filename: file.filename,
        subfolder: file.subfolder,
        size_id: sizeId,
        size_name: size.name,
        finish,
        quantity: 1,
        unit_price: price
      }]);
    }
    toast.success(`Added ${file.filename} to cart`);
  };

  const updateQuantity = (index, delta) => {
    setCart(cart.map((item, i) => {
      if (i !== index) return item;
      const newQty = item.quantity + delta;
      return newQty > 0 ? { ...item, quantity: newQty } : item;
    }));
  };

  const removeFromCart = (index) => {
    setCart(cart.filter((_, i) => i !== index));
  };

  const scrollToCart = () => {
    cartRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const subtotal = cart.reduce((sum, item) => sum + (item.unit_price * item.quantity), 0);
  const total = subtotal + (cart.length > 0 ? shippingCost : 0);

  const handleCheckout = async () => {
    if (!email || !email.includes('@')) {
      toast.error("Please enter a valid email address");
      return;
    }
    if (cart.length === 0) {
      toast.error("Your cart is empty");
      return;
    }
    if (subtotal < MINIMUM_ORDER) {
      toast.error(`Minimum order is £${MINIMUM_ORDER.toFixed(2)} (excluding shipping)`);
      return;
    }

    setSubmitting(true);
    try {
      const orderData = {
        gallery_id: galleryId,
        customer_email: email,
        items: cart.map(item => ({
          file_id: item.file_id,
          size_id: item.size_id,
          finish: item.finish,
          quantity: item.quantity
        }))
      };

      const res = await createPrintOrder(token, orderData);
      
      // Create PayPal payment URL
      // For now, we'll show order confirmation with PayPal payment instructions
      setOrderComplete({
        order_id: res.data.order_id,
        total: res.data.total,
        items: res.data.items
      });
      
      setCart([]);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create order");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#FDFCF8' }}>
        <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Order complete view
  if (orderComplete) {
    const paypalLink = `https://paypal.me/weddingsbymark/${orderComplete.total.toFixed(2)}GBP`;
    
    return (
      <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
        <div className="max-w-lg mx-auto px-6 py-12 text-center">
          <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-green-100 flex items-center justify-center">
            <Check className="w-8 h-8 text-green-600" />
          </div>
          <h1 className="text-3xl mb-4 font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Order Received!</h1>
          <p className="text-[#57534E] mb-6" style={{ fontFamily: 'Manrope, sans-serif' }}>
            Your print order has been submitted. Please complete payment via PayPal to confirm your order.
          </p>
          
          <div className="border rounded-sm p-6 mb-6 text-left" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
            <p className="text-xs uppercase text-[#A8A29E] mb-2">Order Total</p>
            <p className="text-3xl font-bold mb-4">£{orderComplete.total.toFixed(2)}</p>
            
            <p className="text-xs text-[#A8A29E] mb-4">
              Order reference: <code className="bg-[#F5F2EB] px-2 py-1 font-mono">{orderComplete.order_id.slice(0,8).toUpperCase()}</code>
            </p>
            <p className="text-sm text-[#57534E] mb-2">
              Please include your order reference in the PayPal payment note.
            </p>
          </div>

          <a href={paypalLink} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 bg-[#0070BA] text-white rounded-sm px-8 py-3 text-sm font-bold tracking-wider uppercase mb-4 hover:bg-[#003087] transition-colors">
            Pay with PayPal
          </a>
          
          <p className="text-xs text-[#A8A29E] mb-6">
            You'll be redirected to PayPal to complete your payment of £{orderComplete.total.toFixed(2)}
          </p>

          <Button variant="ghost" onClick={() => navigate(`/s/${token}/view`)} className="text-[#57534E]">
            Back to Gallery
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      {/* Header */}
      <header className="sticky top-0 z-40 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.85)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => navigate(`/s/${token}/view`)} className="text-[#57534E] hover:text-[#1C1917]">
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Order Prints</h1>
              <p className="text-xs text-[#A8A29E]">{galleryName}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={scrollToCart} className="flex items-center gap-2 hover:bg-[#F5F2EB] px-3 py-2 rounded-sm transition-colors" data-testid="cart-header-btn">
              <ShoppingCart className="w-4 h-4 text-[#57534E]" />
              <span className="text-sm font-medium">{cart.length} items</span>
              {cart.length > 0 && <span className="text-sm font-bold text-[#D4AF37]">£{subtotal.toFixed(2)}</span>}
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-screen-xl mx-auto px-6 py-8 grid lg:grid-cols-3 gap-8">
        {/* Photos Grid */}
        <div className="lg:col-span-2">
          {printSizes.length === 0 ? (
            <div className="text-center py-12 border rounded-sm" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
              <Printer className="w-12 h-12 mx-auto mb-3 text-[#D4D4D8]" />
              <p className="text-lg" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>Print shop not available</p>
              <p className="text-sm mt-1 text-[#A8A29E]">The photographer hasn't configured print options yet</p>
            </div>
          ) : (
            <>
              <div className="mb-4 p-3 rounded-sm flex items-center gap-3" style={{ backgroundColor: 'rgba(212,175,55,0.08)', border: '1px solid rgba(212,175,55,0.2)' }}>
                <Printer className="w-5 h-5 text-[#D4AF37] flex-shrink-0" />
                <p className="text-sm" style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
                  <strong>Minimum order: £{MINIMUM_ORDER.toFixed(2)}</strong> — Select your photos, choose size and finish, then add to cart.
                </p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {files.map(file => (
                  <PhotoCard key={file.id} file={file} galleryId={galleryId} printSizes={printSizes} onAdd={addToCart} />
                ))}
              </div>
            </>
          )}
        </div>

        {/* Cart Sidebar */}
        <div className="lg:col-span-1" ref={cartRef}>
          <div className="sticky top-24 border rounded-sm p-4" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
            <h2 className="text-lg font-medium mb-4" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Your Cart</h2>
            
            {cart.length === 0 ? (
              <p className="text-sm text-[#A8A29E] py-8 text-center">Your cart is empty</p>
            ) : (
              <div className="space-y-3 mb-4">
                {cart.map((item, i) => (
                  <div key={i} className="flex items-start gap-3 p-2" style={{ backgroundColor: '#F5F2EB' }}>
                    <div className="flex-1">
                      <p className="text-xs font-medium truncate">{item.filename}</p>
                      <p className="text-xs text-[#57534E]">{item.size_name} • {item.finish}</p>
                      <p className="text-xs font-bold">£{(item.unit_price * item.quantity).toFixed(2)}</p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => updateQuantity(i, -1)} className="p-1 text-[#57534E]">
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="text-xs w-6 text-center">{item.quantity}</span>
                      <button onClick={() => updateQuantity(i, 1)} className="p-1 text-[#57534E]">
                        <Plus className="w-3 h-3" />
                      </button>
                      <button onClick={() => removeFromCart(i)} className="p-1 text-[#9F1239] ml-1">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {cart.length > 0 && (
              <>
                <div className="border-t pt-3 space-y-1 text-sm" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
                  <div className="flex justify-between">
                    <span>Subtotal</span>
                    <span>£{subtotal.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Shipping (UK)</span>
                    <span>£{shippingCost.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between font-bold text-base pt-2">
                    <span>Total</span>
                    <span>£{total.toFixed(2)}</span>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs uppercase text-[#57534E]">Your Email</Label>
                    <Input type="email" value={email} onChange={e => setEmail(e.target.value)}
                      placeholder="your@email.com" className="border-[#D4D4D8] rounded-sm" />
                  </div>
                  {subtotal < MINIMUM_ORDER && cart.length > 0 && (
                    <div className="p-3 rounded-sm text-center" style={{ backgroundColor: 'rgba(212,175,55,0.1)', border: '1px solid rgba(212,175,55,0.3)' }}>
                      <p className="text-sm font-medium" style={{ color: '#92400E' }}>
                        Minimum order: £{MINIMUM_ORDER.toFixed(2)}
                      </p>
                      <p className="text-xs" style={{ color: '#A8A29E' }}>
                        Add £{(MINIMUM_ORDER - subtotal).toFixed(2)} more to checkout
                      </p>
                    </div>
                  )}
                  <Button 
                    onClick={handleCheckout} 
                    disabled={submitting || subtotal < MINIMUM_ORDER} 
                    className={`w-full rounded-sm ${subtotal >= MINIMUM_ORDER ? 'bg-[#1C1917] text-[#FDFCF8]' : 'bg-gray-300 text-gray-500 cursor-not-allowed'}`}
                  >
                    {submitting ? "Processing..." : "Checkout with PayPal"}
                  </Button>
                  <p className="text-xs text-center text-[#A8A29E]">
                    You'll be redirected to PayPal to complete payment
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Floating Cart Button for Mobile */}
      {cart.length > 0 && (
        <button 
          onClick={scrollToCart}
          className="lg:hidden fixed bottom-6 right-6 bg-[#D4AF37] text-white px-5 py-3 rounded-full shadow-lg flex items-center gap-2 z-50"
          data-testid="floating-cart-btn"
        >
          <ShoppingCart className="w-5 h-5" />
          <span className="font-bold">{cart.length}</span>
          <span className="text-sm">• £{subtotal.toFixed(2)}</span>
        </button>
      )}
    </div>
  );
}

// Photo card component with add-to-cart functionality
function PhotoCard({ file, galleryId, printSizes, onAdd }) {
  const [selectedSize, setSelectedSize] = useState(printSizes[0]?.id || "");
  const [selectedFinish, setSelectedFinish] = useState("gloss");

  const handleAdd = () => {
    if (!selectedSize) {
      toast.error("Please select a size");
      return;
    }
    onAdd(file, selectedSize, selectedFinish);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} 
      className="border rounded-sm overflow-hidden" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
      <div className="aspect-square relative">
        <img src={previewUrl(galleryId, file.subfolder, file.filename)} alt={file.filename}
          className="w-full h-full object-cover" loading="lazy" />
      </div>
      <div className="p-3 space-y-2">
        <p className="text-xs truncate font-medium">{file.filename}</p>
        
        <Select value={selectedSize} onValueChange={setSelectedSize}>
          <SelectTrigger className="h-8 text-xs">
            <SelectValue placeholder="Select size" />
          </SelectTrigger>
          <SelectContent>
            {printSizes.map(size => (
              <SelectItem key={size.id} value={size.id}>{size.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex gap-1">
          {["gloss", "luster", "silk"].map(finish => (
            <button key={finish} onClick={() => setSelectedFinish(finish)}
              className={`flex-1 text-xs py-1.5 border capitalize ${
                selectedFinish === finish ? 'border-[#D4AF37] bg-[#D4AF37]/5 font-bold' : 'border-[#E5E5E5]'
              }`}>
              {finish}
            </button>
          ))}
        </div>

        {selectedSize && (
          <p className="text-xs text-center text-[#57534E]">
            £{printSizes.find(s => s.id === selectedSize)?.prices[selectedFinish]?.toFixed(2) || '0.00'}
          </p>
        )}

        <Button onClick={handleAdd} size="sm" className="w-full bg-[#1C1917] text-[#FDFCF8] text-xs">
          <Plus className="w-3 h-3 mr-1" /> Add to Cart
        </Button>
      </div>
    </motion.div>
  );
}
