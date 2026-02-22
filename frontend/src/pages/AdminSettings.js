import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle
} from "@/components/ui/alert-dialog";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from "@/components/ui/dialog";
import {
  ArrowLeft, Key, Package, Plus, Pencil, Trash2, Printer, Eye, Check, Film
} from "lucide-react";
import {
  changePassword, getPrintSizes, createPrintSize, updatePrintSize, deletePrintSize,
  getPrintOrders, updateOrderStatus, getCompressionSetting, setCompressionSetting
} from "@/lib/api";

export default function AdminSettings() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("password");

  // Password change
  const [passwordForm, setPasswordForm] = useState({
    current_password: "", new_password: "", confirm_password: ""
  });
  const [changingPassword, setChangingPassword] = useState(false);

  // Print sizes
  const [printSizes, setPrintSizes] = useState([]);
  const [loadingSizes, setLoadingSizes] = useState(false);
  const [showSizeDialog, setShowSizeDialog] = useState(false);
  const [editingSize, setEditingSize] = useState(null);
  const [sizeForm, setSizeForm] = useState({
    name: "", gloss_price: "", luster_price: "", silk_price: ""
  });
  const [deleteSizeTarget, setDeleteSizeTarget] = useState(null);

  // Print orders
  const [orders, setOrders] = useState([]);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState(null);

  // Video compression
  const [compressionEnabled, setCompressionEnabled] = useState(false);
  const [compressionThreshold, setCompressionThreshold] = useState(200);
  const [loadingCompression, setLoadingCompression] = useState(false);
  const [togglingCompression, setTogglingCompression] = useState(false);

  useEffect(() => {
    if (activeTab === "print-sizes") loadPrintSizes();
    if (activeTab === "orders") loadOrders();
    if (activeTab === "video") loadCompressionSetting();
  }, [activeTab]);

  const loadPrintSizes = async () => {
    setLoadingSizes(true);
    try {
      const res = await getPrintSizes();
      setPrintSizes(res.data);
    } catch { toast.error("Failed to load print sizes"); }
    finally { setLoadingSizes(false); }
  };

  const loadOrders = async () => {
    setLoadingOrders(true);
    try {
      const res = await getPrintOrders();
      setOrders(res.data);
    } catch { toast.error("Failed to load orders"); }
    finally { setLoadingOrders(false); }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      toast.error("New passwords don't match");
      return;
    }
    if (passwordForm.new_password.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    setChangingPassword(true);
    try {
      await changePassword({
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password
      });
      toast.success("Password changed successfully");
      setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to change password");
    } finally {
      setChangingPassword(false);
    }
  };

  const handleSavePrintSize = async () => {
    if (!sizeForm.name || !sizeForm.gloss_price || !sizeForm.luster_price || !sizeForm.silk_price) {
      toast.error("All fields are required");
      return;
    }
    try {
      const data = {
        name: sizeForm.name,
        gloss_price: parseFloat(sizeForm.gloss_price),
        luster_price: parseFloat(sizeForm.luster_price),
        silk_price: parseFloat(sizeForm.silk_price)
      };
      if (editingSize) {
        await updatePrintSize(editingSize.id, data);
        toast.success("Print size updated");
      } else {
        await createPrintSize(data);
        toast.success("Print size created");
      }
      setShowSizeDialog(false);
      setEditingSize(null);
      setSizeForm({ name: "", gloss_price: "", luster_price: "", silk_price: "" });
      loadPrintSizes();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    }
  };

  const handleDeleteSize = async () => {
    try {
      await deletePrintSize(deleteSizeTarget.id);
      toast.success("Print size deleted");
      setDeleteSizeTarget(null);
      loadPrintSizes();
    } catch { toast.error("Failed to delete"); }
  };

  const handleUpdateOrderStatus = async (orderId, status) => {
    try {
      await updateOrderStatus(orderId, status);
      toast.success(`Order marked as ${status}`);
      loadOrders();
    } catch { toast.error("Failed to update status"); }
  };

  const openEditSize = (size) => {
    setEditingSize(size);
    setSizeForm({
      name: size.name,
      gloss_price: size.prices.gloss.toString(),
      luster_price: size.prices.luster.toString(),
      silk_price: size.prices.silk.toString()
    });
    setShowSizeDialog(true);
  };

  const openNewSize = () => {
    setEditingSize(null);
    setSizeForm({ name: "", gloss_price: "", luster_price: "", silk_price: "" });
    setShowSizeDialog(true);
  };

  const formatPrice = (price) => `£${price.toFixed(2)}`;
  const formatDate = (dateStr) => new Date(dateStr).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });

  const statusColors = {
    pending: "bg-yellow-100 text-yellow-800",
    paid: "bg-blue-100 text-blue-800",
    processing: "bg-purple-100 text-purple-800",
    printed: "bg-indigo-100 text-indigo-800",
    shipped: "bg-green-100 text-green-800",
    completed: "bg-emerald-100 text-emerald-800",
    cancelled: "bg-red-100 text-red-800"
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FDFCF8' }}>
      {/* Header */}
      <header className="sticky top-0 z-50 border-b" style={{ backgroundColor: 'rgba(253,252,248,0.9)', backdropFilter: 'blur(16px)', borderColor: 'rgba(212,175,55,0.15)' }}>
        <div className="max-w-screen-xl mx-auto px-6 py-4 flex items-center gap-4">
          <button onClick={() => navigate("/admin/dashboard")} className="text-[#57534E] hover:text-[#1C1917]">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>Settings</h1>
        </div>
      </header>

      <main className="max-w-screen-xl mx-auto px-6 py-8">
        {/* Tabs */}
        <div className="flex gap-2 mb-8 border-b" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
          {[
            { id: "password", label: "Change Password", icon: Key },
            { id: "print-sizes", label: "Print Sizes & Prices", icon: Printer },
            { id: "orders", label: "Print Orders", icon: Package }
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-[1px] transition-colors ${
                activeTab === tab.id 
                  ? 'border-[#D4AF37] text-[#1C1917]' 
                  : 'border-transparent text-[#57534E] hover:text-[#1C1917]'
              }`}
              style={{ fontFamily: 'Manrope, sans-serif' }}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Password Change Tab */}
        {activeTab === "password" && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="max-w-md">
            <form onSubmit={handlePasswordChange} className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Current Password</Label>
                <Input type="password" data-testid="current-password" value={passwordForm.current_password}
                  onChange={e => setPasswordForm(f => ({...f, current_password: e.target.value}))}
                  className="border-[#D4D4D8] rounded-sm" required />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>New Password</Label>
                <Input type="password" data-testid="new-password" value={passwordForm.new_password}
                  onChange={e => setPasswordForm(f => ({...f, new_password: e.target.value}))}
                  className="border-[#D4D4D8] rounded-sm" required minLength={6} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Confirm New Password</Label>
                <Input type="password" data-testid="confirm-password" value={passwordForm.confirm_password}
                  onChange={e => setPasswordForm(f => ({...f, confirm_password: e.target.value}))}
                  className="border-[#D4D4D8] rounded-sm" required minLength={6} />
              </div>
              <Button type="submit" disabled={changingPassword} data-testid="change-password-btn"
                className="bg-[#1C1917] text-[#FDFCF8] rounded-sm px-6 py-2 text-xs tracking-wider uppercase font-bold">
                {changingPassword ? "Changing..." : "Change Password"}
              </Button>
            </form>
          </motion.div>
        )}

        {/* Print Sizes Tab */}
        {activeTab === "print-sizes" && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="flex items-center justify-between mb-6">
              <p className="text-sm text-[#57534E]" style={{ fontFamily: 'Manrope, sans-serif' }}>
                Configure print sizes and prices for each finish type. Shipping: £2.50 (UK only)
              </p>
              <Button onClick={openNewSize} data-testid="add-print-size-btn"
                className="bg-[#1C1917] text-[#FDFCF8] rounded-sm px-4 py-2 text-xs tracking-wider uppercase font-bold gap-2">
                <Plus className="w-3.5 h-3.5" /> Add Size
              </Button>
            </div>

            {loadingSizes ? (
              <div className="flex justify-center py-12">
                <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : printSizes.length === 0 ? (
              <div className="text-center py-12 border rounded-sm" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
                <Printer className="w-12 h-12 mx-auto mb-3 text-[#D4D4D8]" />
                <p className="text-lg" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>No print sizes configured</p>
                <p className="text-sm mt-1 text-[#A8A29E]">Add print sizes to enable the print shop for your couples</p>
              </div>
            ) : (
              <div className="border rounded-sm overflow-hidden" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
                <table className="w-full">
                  <thead>
                    <tr style={{ backgroundColor: '#F5F2EB' }}>
                      <th className="text-left px-4 py-3 text-xs tracking-wider uppercase font-bold" style={{ color: '#57534E' }}>Size</th>
                      <th className="text-right px-4 py-3 text-xs tracking-wider uppercase font-bold" style={{ color: '#57534E' }}>Gloss</th>
                      <th className="text-right px-4 py-3 text-xs tracking-wider uppercase font-bold" style={{ color: '#57534E' }}>Luster</th>
                      <th className="text-right px-4 py-3 text-xs tracking-wider uppercase font-bold" style={{ color: '#57534E' }}>Silk</th>
                      <th className="w-24"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {printSizes.map(size => (
                      <tr key={size.id} className="border-t" style={{ borderColor: 'rgba(212,175,55,0.1)' }}>
                        <td className="px-4 py-3 font-medium" style={{ fontFamily: 'Manrope, sans-serif' }}>{size.name}</td>
                        <td className="px-4 py-3 text-right text-sm">{formatPrice(size.prices.gloss)}</td>
                        <td className="px-4 py-3 text-right text-sm">{formatPrice(size.prices.luster)}</td>
                        <td className="px-4 py-3 text-right text-sm">{formatPrice(size.prices.silk)}</td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            <button onClick={() => openEditSize(size)} className="p-1.5 text-[#57534E] hover:text-[#1C1917]">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => setDeleteSizeTarget(size)} className="p-1.5 text-[#9F1239]">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        )}

        {/* Print Orders Tab */}
        {activeTab === "orders" && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            {loadingOrders ? (
              <div className="flex justify-center py-12">
                <div className="w-8 h-8 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : orders.length === 0 ? (
              <div className="text-center py-12 border rounded-sm" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
                <Package className="w-12 h-12 mx-auto mb-3 text-[#D4D4D8]" />
                <p className="text-lg" style={{ fontFamily: 'Cormorant Garamond, serif', color: '#57534E' }}>No orders yet</p>
                <p className="text-sm mt-1 text-[#A8A29E]">Orders will appear here when couples purchase prints</p>
              </div>
            ) : (
              <div className="space-y-4">
                {orders.map(order => (
                  <div key={order.id} className="border rounded-sm p-4" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <p className="font-medium" style={{ fontFamily: 'Manrope, sans-serif' }}>{order.gallery_name}</p>
                        <p className="text-xs text-[#A8A29E]">{order.customer_email} &middot; {formatDate(order.created_at)}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-1 text-xs font-bold uppercase rounded ${statusColors[order.status] || 'bg-gray-100'}`}>
                          {order.status}
                        </span>
                        <span className="font-bold" style={{ fontFamily: 'Manrope, sans-serif' }}>£{order.total.toFixed(2)}</span>
                      </div>
                    </div>
                    
                    <div className="text-sm mb-3">
                      <p className="text-[#57534E]">{order.items.length} item(s): {order.items.map(i => `${i.quantity}x ${i.size_name} ${i.finish}`).join(', ')}</p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setSelectedOrder(order)} className="text-xs gap-1">
                        <Eye className="w-3 h-3" /> View Details
                      </Button>
                      {order.status === 'paid' && (
                        <Button size="sm" onClick={() => handleUpdateOrderStatus(order.id, 'processing')} 
                          className="bg-purple-600 text-white text-xs gap-1">
                          <Check className="w-3 h-3" /> Mark Processing
                        </Button>
                      )}
                      {order.status === 'processing' && (
                        <Button size="sm" onClick={() => handleUpdateOrderStatus(order.id, 'printed')}
                          className="bg-indigo-600 text-white text-xs gap-1">
                          <Check className="w-3 h-3" /> Mark Printed
                        </Button>
                      )}
                      {order.status === 'printed' && (
                        <Button size="sm" onClick={() => handleUpdateOrderStatus(order.id, 'shipped')}
                          className="bg-green-600 text-white text-xs gap-1">
                          <Check className="w-3 h-3" /> Mark Shipped
                        </Button>
                      )}
                      {order.status === 'shipped' && (
                        <Button size="sm" onClick={() => handleUpdateOrderStatus(order.id, 'completed')}
                          className="bg-emerald-600 text-white text-xs gap-1">
                          <Check className="w-3 h-3" /> Mark Complete
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </main>

      {/* Add/Edit Print Size Dialog */}
      <Dialog open={showSizeDialog} onOpenChange={setShowSizeDialog}>
        <DialogContent className="border-none shadow-2xl rounded-none max-w-md" style={{ backgroundColor: '#FDFCF8' }}>
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              {editingSize ? "Edit Print Size" : "Add Print Size"}
            </DialogTitle>
            <DialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              Set the size name and prices for each finish type
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-1.5">
              <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Size Name</Label>
              <Input data-testid="size-name" value={sizeForm.name} 
                onChange={e => setSizeForm(f => ({...f, name: e.target.value}))}
                placeholder="e.g. 6x4, 7x5, 10x8" className="border-[#D4D4D8] rounded-sm" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Gloss (£)</Label>
                <Input type="number" step="0.01" data-testid="gloss-price" value={sizeForm.gloss_price}
                  onChange={e => setSizeForm(f => ({...f, gloss_price: e.target.value}))}
                  placeholder="5.00" className="border-[#D4D4D8] rounded-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Luster (£)</Label>
                <Input type="number" step="0.01" data-testid="luster-price" value={sizeForm.luster_price}
                  onChange={e => setSizeForm(f => ({...f, luster_price: e.target.value}))}
                  placeholder="6.00" className="border-[#D4D4D8] rounded-sm" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs tracking-[0.1em] uppercase font-semibold" style={{ color: '#57534E' }}>Silk (£)</Label>
                <Input type="number" step="0.01" data-testid="silk-price" value={sizeForm.silk_price}
                  onChange={e => setSizeForm(f => ({...f, silk_price: e.target.value}))}
                  placeholder="6.50" className="border-[#D4D4D8] rounded-sm" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowSizeDialog(false)} className="rounded-sm">Cancel</Button>
            <Button onClick={handleSavePrintSize} data-testid="save-size-btn"
              className="bg-[#1C1917] text-[#FDFCF8] rounded-sm px-6 text-xs tracking-wider uppercase font-bold">
              {editingSize ? "Update" : "Add Size"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Size Confirmation */}
      <AlertDialog open={!!deleteSizeTarget} onOpenChange={() => setDeleteSizeTarget(null)}>
        <AlertDialogContent className="border-none shadow-2xl rounded-none" style={{ backgroundColor: '#FDFCF8' }}>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              Delete "{deleteSizeTarget?.name}"?
            </AlertDialogTitle>
            <AlertDialogDescription style={{ color: '#57534E', fontFamily: 'Manrope, sans-serif' }}>
              This will remove this print size option from the shop.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-sm">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteSize}
              className="bg-[#9F1239] text-white hover:bg-[#9F1239]/90 rounded-sm text-xs tracking-wider uppercase font-bold">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Order Details Dialog */}
      <Dialog open={!!selectedOrder} onOpenChange={() => setSelectedOrder(null)}>
        <DialogContent className="border-none shadow-2xl rounded-none max-w-lg" style={{ backgroundColor: '#FDFCF8' }}>
          <DialogHeader>
            <DialogTitle className="text-2xl font-medium" style={{ fontFamily: 'Cormorant Garamond, serif' }}>
              Order Details
            </DialogTitle>
          </DialogHeader>
          {selectedOrder && (
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-xs uppercase text-[#A8A29E] mb-1">Gallery</p>
                  <p className="font-medium">{selectedOrder.gallery_name}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-[#A8A29E] mb-1">Customer</p>
                  <p className="font-medium">{selectedOrder.customer_email}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-[#A8A29E] mb-1">Order Date</p>
                  <p>{formatDate(selectedOrder.created_at)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-[#A8A29E] mb-1">PayPal ID</p>
                  <p className="font-mono text-xs">{selectedOrder.paypal_order_id || 'N/A'}</p>
                </div>
              </div>

              <div className="border-t pt-4" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
                <p className="text-xs uppercase text-[#A8A29E] mb-2">Items</p>
                <div className="space-y-2">
                  {selectedOrder.items.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm p-2" style={{ backgroundColor: '#F5F2EB' }}>
                      <div>
                        <p className="font-medium">{item.filename}</p>
                        <p className="text-xs text-[#57534E]">{item.size_name} • {item.finish} • Qty: {item.quantity}</p>
                      </div>
                      <p className="font-medium">£{item.total.toFixed(2)}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border-t pt-4 space-y-1 text-sm" style={{ borderColor: 'rgba(212,175,55,0.15)' }}>
                <div className="flex justify-between">
                  <span>Subtotal</span>
                  <span>£{selectedOrder.subtotal.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Shipping</span>
                  <span>£{selectedOrder.shipping.toFixed(2)}</span>
                </div>
                <div className="flex justify-between font-bold text-base pt-2">
                  <span>Total</span>
                  <span>£{selectedOrder.total.toFixed(2)}</span>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
