"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import styles from "./FavoriteVerses.module.css";

interface FavoriteVerse {
  reference: string;
  displayRef: string;
}

const DEFAULT_FAVORITES: FavoriteVerse[] = [
  { reference: "Romans.8.28-30", displayRef: "Rom. 8:28-30" },
  { reference: "John.3.16", displayRef: "John 3:16" },
  { reference: "Ephesians.2.8-9", displayRef: "Eph. 2:8-9" },
];

export function FavoriteVerses() {
  const [favorites, setFavorites] = useState<FavoriteVerse[]>([]);
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    // Load favorites from localStorage
    const saved = localStorage.getItem("favoriteVerses");
    if (saved) {
      try {
        setFavorites(JSON.parse(saved));
      } catch {
        setFavorites(DEFAULT_FAVORITES);
      }
    } else {
      setFavorites(DEFAULT_FAVORITES);
    }
  }, []);

  const handleRemove = (reference: string) => {
    const updated = favorites.filter((v) => v.reference !== reference);
    setFavorites(updated);
    localStorage.setItem("favoriteVerses", JSON.stringify(updated));
  };

  return (
    <section className={styles.section}>
      <div className={styles.header}>
        <h2 className={styles.title}>⭐ Favorite Verses</h2>
        <button
          className={styles.editButton}
          onClick={() => setIsEditing(!isEditing)}
        >
          {isEditing ? "Done" : "Edit"}
        </button>
      </div>

      {favorites.length === 0 ? (
        <div className={styles.empty}>
          <p>No favorite verses yet</p>
          <p className={styles.emptyHint}>
            Pin verses for quick access from verse explorer
          </p>
        </div>
      ) : (
        <div className={styles.list}>
          {favorites.map((verse) => (
            <div key={verse.reference} className={styles.verseItem}>
              <Link
                href={`/verse/${verse.reference}`}
                className={styles.verseLink}
              >
                📖 {verse.displayRef}
              </Link>
              {isEditing && (
                <button
                  className={styles.removeButton}
                  onClick={() => handleRemove(verse.reference)}
                  aria-label={`Remove ${verse.displayRef}`}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!isEditing && (
        <Link href="/verse/John.1.1" className={styles.addButton}>
          + Add verse
        </Link>
      )}
    </section>
  );
}
