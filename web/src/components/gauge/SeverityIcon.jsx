import { CheckCircle2, AlertTriangle, AlertOctagon } from "lucide-react";
import clsx from "clsx";

const MAP = {
  normal:  { Icon: CheckCircle2,  cls: "text-severity-normal bg-severity-normal/10" },
  warning: { Icon: AlertTriangle, cls: "text-severity-warning bg-severity-warning/10" },
  alert:   { Icon: AlertOctagon,  cls: "text-severity-alert   bg-severity-alert/15" },
};

export function SeverityIcon({ severity, size = "md" }) {
  const { Icon, cls } = MAP[severity] || MAP.normal;
  const dim = size === "lg" ? "h-14 w-14" : "h-10 w-10";
  return (
    <div className={clsx("grid place-items-center rounded-2xl transition-colors", dim, cls)}>
      <Icon className="h-2/3 w-2/3" />
    </div>
  );
}
