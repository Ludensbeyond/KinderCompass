"use client";

import { useEffect, useRef } from "react";
import type { LayerGroup, Map as LeafletMap } from "leaflet";

export type MapPoint = {
  name: string;
  type: "home" | "preschool";
  latitude: number;
  longitude: number;
};

export default function LiveMap({ points }: { points: MapPoint[] }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const markers = useRef<LayerGroup | null>(null);

  useEffect(() => {
    let active = true;
    void import("leaflet").then((L) => {
      if (!active || !container.current) return;
      if (!map.current) {
        map.current = L.map(container.current, { zoomControl: true }).setView([1.3521, 103.8198], 11);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 19,
        }).addTo(map.current);
      }

      markers.current?.remove();
      const routeLayer = L.layerGroup().addTo(map.current);
      markers.current = routeLayer;
      const colours = { home: "#176b5a", preschool: "#e87d5b" };
      const coordinates = points.map((point) => [point.latitude, point.longitude] as L.LatLngTuple);

      points.forEach((point) => {
        const popup = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = point.name;
        popup.append(title, document.createElement("br"), document.createTextNode(point.type));
        L.circleMarker([point.latitude, point.longitude], {
          radius: 8,
          color: "#fffdf8",
          weight: 3,
          fillColor: colours[point.type],
          fillOpacity: 1,
        }).bindPopup(popup).addTo(routeLayer);
      });

      if (coordinates.length > 1) {
        coordinates.slice(1).forEach((preschool) => {
          L.polyline([coordinates[0], preschool], { color: "#176b5a", weight: 4, opacity: 0.8, dashArray: "8 7" }).addTo(routeLayer);
        });
      }
      if (coordinates.length) {
        map.current.fitBounds(L.latLngBounds(coordinates).pad(0.25), { maxZoom: 15 });
      }
      setTimeout(() => map.current?.invalidateSize(), 0);

    });
    return () => { active = false; };
  }, [points]);

  useEffect(() => () => {
    map.current?.remove();
    map.current = null;
    markers.current = null;
  }, []);

  return <div className="leafletCanvas" ref={container} aria-label="Interactive route map" />;
}
