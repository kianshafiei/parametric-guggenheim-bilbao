#! python3
"""Recording layout: Rhino on the left half, Grasshopper on the right half, canvas framed."""
import System.Drawing as SD
import System.Windows.Forms as WF
import Grasshopper as gh
wa = WF.Screen.PrimaryScreen.WorkingArea
ed = gh.Instances.DocumentEditor
ed.WindowState = WF.FormWindowState.Normal
ed.Bounds = SD.Rectangle(wa.Left + wa.Width // 2, wa.Top, wa.Width - wa.Width // 2, wa.Height)
cv = gh.Instances.ActiveCanvas
doc = cv.Document
rs = [o.Attributes.Bounds for o in doc.Objects]
x0 = min(r.Left for r in rs); y0 = min(r.Top for r in rs)
x1 = max(r.Right for r in rs); y1 = max(r.Bottom for r in rs)
W, H = cv.Width, cv.Height
z = min(W / ((x1 - x0) * 1.08), H / ((y1 - y0) * 1.1))
cv.Viewport.Zoom = float(z)
cv.Viewport.MidPoint = SD.PointF((x0 + x1) / 2.0, (y0 + y1) / 2.0)
cv.Refresh()
print("layout ok", wa, z)
