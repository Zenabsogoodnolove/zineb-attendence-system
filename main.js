// Fichier JS principal
console.log('ISCAE Présence - Application chargée');

// Fonction pour confirmer les actions
function confirmAction(message) {
    return confirm(message);
}

// Gestion des erreurs AJAX
async function fetchWithErrorHandling(url, options = {}) {
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Erreur:', error);
        alert('Une erreur est survenue. Veuillez réessayer.');
        return null;
    }
}