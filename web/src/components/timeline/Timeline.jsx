import { Card } from "../ui/Card.jsx";
import { EventRow } from "./EventRow.jsx";

export function Timeline({ events }) {
  return (
    <Card title="Eventos">
      <div className="flex max-h-[360px] flex-col gap-2 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="px-2 py-6 text-center text-xs text-text-2">
            Nenhum evento ainda — quando o detector disparar, aparece aqui.
          </div>
        ) : (
          events.map((e, i) => <EventRow key={`${e.timestamp}-${i}`} event={e} />)
        )}
      </div>
    </Card>
  );
}
