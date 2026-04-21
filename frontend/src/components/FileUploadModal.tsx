"use client";

import { FormEvent, useState } from "react";
import { Button, Form, Modal } from "react-bootstrap";

type Props = {
  show: boolean;
  isSubmitting: boolean;
  onHide: () => void;
  onSubmit: (title: string, file: File) => Promise<void>;
};

export function FileUploadModal({ show, isSubmitting, onHide, onSubmit }: Props) {
  const [title, setTitle] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  function handleHide() {
    setTitle("");
    setSelectedFile(null);
    onHide();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !selectedFile) return;
    await onSubmit(title, selectedFile);
    setTitle("");
    setSelectedFile(null);
  }

  return (
    <Modal show={show} onHide={handleHide} centered>
      <Form onSubmit={handleSubmit}>
        <Modal.Header closeButton>
          <Modal.Title>Добавить файл</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form.Group className="mb-3">
            <Form.Label>Название</Form.Label>
            <Form.Control
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Например, Договор с подрядчиком"
            />
          </Form.Group>
          <Form.Group>
            <Form.Label>Файл</Form.Label>
            <Form.Control
              type="file"
              onChange={(e) =>
                setSelectedFile((e.target as HTMLInputElement).files?.[0] ?? null)
              }
            />
          </Form.Group>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-secondary" onClick={handleHide}>
            Отмена
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={isSubmitting || !title.trim() || !selectedFile}
          >
            {isSubmitting ? "Загрузка..." : "Сохранить"}
          </Button>
        </Modal.Footer>
      </Form>
    </Modal>
  );
}
