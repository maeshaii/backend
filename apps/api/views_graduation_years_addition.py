# Add this function to the END of backend/apps/api/views.py

@api_view(["GET"])
@permission_classes([AllowAny])
def graduation_years_view(request):
    """
    Get all unique graduation years from alumni data for dropdowns.
    Used by: Frontend statistics page, mobile app filters
    
    Returns:
        JSON: {
            'success': bool,
            'years': list[str]  # Sorted years in descending order
        }
    """
    try:
        year_values = (
            User.objects
            .filter(account_type__user=True)
            .values_list('academic_info__year_graduated', flat=True)
            .distinct()
        )
        years = [str(year) for year in sorted(year_values, reverse=True) if year is not None]
        
        logger.info(f"Fetched {len(years)} graduation years")
        
        return JsonResponse({
            'success': True,
            'years': years
        })
    except Exception as e:
        logger.error(f"Error fetching graduation years: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'Failed to fetch graduation years',
            'error': str(e)
        }, status=500)

