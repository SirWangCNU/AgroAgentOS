interface LoadingGridProps {
  rows?: number;
  cols?: number;
  height?: string;
}

export default function LoadingGrid({
  rows = 3,
  cols = 1,
  height = "h-16",
}: LoadingGridProps) {
  return (
    <div
      className="grid gap-3"
      style={{
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
      }}
    >
      {Array.from({ length: rows * cols }).map((_, i) => (
        <div key={i} className={`${height} skeleton rounded-xl`} />
      ))}
    </div>
  );
}
