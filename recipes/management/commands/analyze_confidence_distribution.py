#!/usr/bin/env python3
"""
Django management command to analyze confidence distribution across recipes
and provide insights for hybrid approach performance evaluation.
"""

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Min, Max, StdDev
from django.db.models.functions import Round
from recipes.models import Recipe, AllergenAnalysisResult
import json
from collections import defaultdict
# import matplotlib.pyplot as plt  # Uncomment if matplotlib is available
# import numpy as np  # Uncomment if numpy is available
from datetime import datetime
import os


class Command(BaseCommand):
    help = 'Analyze confidence distribution across recipes and processing performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='output',
            help='Directory to save analysis outputs (default: output)'
        )
        parser.add_argument(
            '--save-charts',
            action='store_true',
            help='Save confidence distribution charts'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed statistics for each confidence range'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting confidence distribution analysis...')
        )
        
        # Ensure output directory exists
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        # Analyze confidence distribution
        confidence_stats = self.analyze_confidence_distribution()
        
        # Analyze processing time performance
        processing_stats = self.analyze_processing_performance()
        
        # Generate comprehensive report
        self.generate_report(confidence_stats, processing_stats, output_dir)
        
        # Save charts if requested
        if options['save_charts']:
            self.save_confidence_charts(confidence_stats, output_dir)
        
        # Display summary
        self.display_summary(confidence_stats, processing_stats)
        
        self.stdout.write(
            self.style.SUCCESS('Confidence distribution analysis completed!')
        )

    def analyze_confidence_distribution(self):
        """Analyze confidence scores across all recipes"""
        self.stdout.write('Analyzing confidence distribution...')
        
        # Get analysis results with confidence scores
        results_with_confidence = AllergenAnalysisResult.objects.filter(
            confidence_scores__isnull=False
        ).exclude(confidence_scores={})
        
        total_recipes = Recipe.objects.count()
        results_with_confidence_count = results_with_confidence.count()
        
        if results_with_confidence_count == 0:
            self.stdout.write(
                self.style.WARNING('No analysis results found with confidence scores!')
            )
            return None
        
        # Extract all individual confidence scores from JSON data
        all_confidence_scores = []
        allergen_confidence_data = {}
        
        for result in results_with_confidence:
            if isinstance(result.confidence_scores, dict):
                for allergen, confidence in result.confidence_scores.items():
                    if isinstance(confidence, (int, float)) and confidence > 0:
                        all_confidence_scores.append(confidence)
                        
                        # Track confidence by allergen type
                        if allergen not in allergen_confidence_data:
                            allergen_confidence_data[allergen] = []
                        allergen_confidence_data[allergen].append(confidence)
        
        if not all_confidence_scores:
            self.stdout.write(
                self.style.WARNING('No valid confidence scores found in analysis results!')
            )
            return None
        
        # Calculate basic statistics
        avg_confidence = sum(all_confidence_scores) / len(all_confidence_scores)
        min_confidence = min(all_confidence_scores)
        max_confidence = max(all_confidence_scores)
        
        # Calculate standard deviation
        variance = sum((x - avg_confidence) ** 2 for x in all_confidence_scores) / len(all_confidence_scores)
        std_confidence = variance ** 0.5
        
        confidence_stats = {
            'total_recipes': total_recipes,
            'recipes_with_confidence': results_with_confidence_count,
            'coverage_percentage': (results_with_confidence_count / total_recipes) * 100,
            'total_confidence_scores': len(all_confidence_scores),
            'basic_stats': {
                'avg_confidence': round(avg_confidence, 3),
                'min_confidence': round(min_confidence, 3),
                'max_confidence': round(max_confidence, 3),
                'std_confidence': round(std_confidence, 3)
            },
            'allergen_breakdown': {}
        }
        
        # Analyze confidence by allergen type
        for allergen, scores in allergen_confidence_data.items():
            if scores:
                allergen_avg = sum(scores) / len(scores)
                allergen_min = min(scores)
                allergen_max = max(scores)
                confidence_stats['allergen_breakdown'][allergen] = {
                    'count': len(scores),
                    'avg_confidence': round(allergen_avg, 3),
                    'min_confidence': round(allergen_min, 3),
                    'max_confidence': round(allergen_max, 3)
                }
        
        # Analyze confidence ranges
        confidence_ranges = [
            (0.0, 0.2, 'Very Low (0.0-0.2)'),
            (0.2, 0.4, 'Low (0.2-0.4)'),
            (0.4, 0.6, 'Medium (0.4-0.6)'),
            (0.6, 0.8, 'High (0.6-0.8)'),
            (0.8, 1.0, 'Very High (0.8-1.0)')
        ]
        
        range_analysis = []
        for min_val, max_val, label in confidence_ranges:
            count = sum(1 for score in all_confidence_scores if min_val <= score < max_val)
            percentage = (count / len(all_confidence_scores)) * 100 if all_confidence_scores else 0
            
            range_analysis.append({
                'range': label,
                'min': min_val,
                'max': max_val,
                'count': count,
                'percentage': round(percentage, 2)
            })
        
        confidence_stats['range_analysis'] = range_analysis
        
        # Analyze by confidence level for hybrid approach
        hybrid_thresholds = {
            'high_confidence': 0.8,  # Use NLP only
            'medium_confidence': 0.6,  # Use hybrid approach
            'low_confidence': 0.4,    # Use rule-based approach
            'very_low_confidence': 0.2  # Manual review needed
        }
        
        hybrid_analysis = {}
        for threshold_name, threshold_value in hybrid_thresholds.items():
            count = sum(1 for score in all_confidence_scores if score >= threshold_value)
            percentage = (count / len(all_confidence_scores)) * 100 if all_confidence_scores else 0
            
            hybrid_analysis[threshold_name] = {
                'threshold': threshold_value,
                'count': count,
                'percentage': round(percentage, 2)
            }
        
        confidence_stats['hybrid_analysis'] = hybrid_analysis
        
        return confidence_stats

    def analyze_processing_performance(self):
        """Analyze processing time performance"""
        self.stdout.write('Analyzing processing performance...')
        
        # Get analysis results with processing time
        results_with_time = AllergenAnalysisResult.objects.filter(
            processing_time__isnull=False
        ).exclude(processing_time=0.0)
        
        total_results = AllergenAnalysisResult.objects.count()
        results_with_time_count = results_with_time.count()
        
        if results_with_time_count == 0:
            self.stdout.write(
                self.style.WARNING('No analysis results found with processing time!')
            )
            return None
        
        # Calculate processing time statistics
        processing_stats = {
            'total_results': total_results,
            'results_with_time': results_with_time_count,
            'coverage_percentage': (results_with_time_count / total_results) * 100,
            'time_stats': results_with_time.aggregate(
                avg_time=Round(Avg('processing_time'), 3),
                min_time=Min('processing_time'),
                max_time=Max('processing_time'),
                std_time=Round(StdDev('processing_time'), 3)
            )
        }
        
        # Analyze processing time ranges
        time_ranges = [
            (0.0, 1.0, 'Fast (<1s)'),
            (1.0, 5.0, 'Medium (1-5s)'),
            (5.0, 10.0, 'Slow (5-10s)'),
            (10.0, float('inf'), 'Very Slow (>10s)')
        ]
        
        time_range_analysis = []
        for min_val, max_val, label in time_ranges:
            if max_val == float('inf'):
                count = results_with_time.filter(processing_time__gte=min_val).count()
            else:
                count = results_with_time.filter(
                    processing_time__gte=min_val,
                    processing_time__lt=max_val
                ).count()
            
            percentage = (count / results_with_time_count) * 100
            
            time_range_analysis.append({
                'range': label,
                'min': min_val,
                'max': max_val if max_val != float('inf') else '∞',
                'count': count,
                'percentage': round(percentage, 2)
            })
        
        processing_stats['time_range_analysis'] = time_range_analysis
        
        return processing_stats

    def generate_report(self, confidence_stats, processing_stats, output_dir):
        """Generate comprehensive analysis report"""
        self.stdout.write('Generating analysis report...')
        
        report = {
            'analysis_date': datetime.now().isoformat(),
            'confidence_analysis': confidence_stats,
            'processing_analysis': processing_stats,
            'recommendations': self.generate_recommendations(confidence_stats, processing_stats)
        }
        
        # Save JSON report
        report_path = os.path.join(output_dir, 'confidence_distribution_report.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        self.stdout.write(f'Report saved to: {report_path}')
        
        # Save text report
        text_report_path = os.path.join(output_dir, 'confidence_distribution_report.txt')
        with open(text_report_path, 'w') as f:
            f.write(self.format_text_report(report))
        
        self.stdout.write(f'Text report saved to: {text_report_path}')

    def generate_recommendations(self, confidence_stats, processing_stats):
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        if confidence_stats:
            # Confidence-based recommendations
            if confidence_stats['coverage_percentage'] < 50:
                recommendations.append({
                    'category': 'Data Quality',
                    'priority': 'High',
                    'recommendation': 'Increase coverage of NLP confidence scores across recipes',
                    'action': 'Ensure all recipe processing includes confidence score calculation'
                })
            
            hybrid_analysis = confidence_stats.get('hybrid_analysis', {})
            if hybrid_analysis.get('high_confidence', {}).get('percentage', 0) < 30:
                recommendations.append({
                    'category': 'Model Performance',
                    'priority': 'Medium',
                    'recommendation': 'Improve NLP model to increase high-confidence predictions',
                    'action': 'Retrain NER model with more diverse training data'
                })
            
            if hybrid_analysis.get('very_low_confidence', {}).get('percentage', 0) > 20:
                recommendations.append({
                    'category': 'Quality Assurance',
                    'priority': 'High',
                    'recommendation': 'High percentage of very low confidence predictions',
                    'action': 'Implement manual review workflow for low-confidence cases'
                })
        
        if processing_stats:
            # Processing time recommendations
            if processing_stats['coverage_percentage'] < 50:
                recommendations.append({
                    'category': 'Performance Monitoring',
                    'priority': 'High',
                    'recommendation': 'Increase coverage of processing time tracking',
                    'action': 'Ensure all analysis operations record processing time'
                })
            
            avg_time = processing_stats.get('time_stats', {}).get('avg_time', 0)
            if avg_time > 5.0:
                recommendations.append({
                    'category': 'Performance Optimization',
                    'priority': 'Medium',
                    'recommendation': 'Average processing time is high',
                    'action': 'Optimize NLP pipeline and consider caching strategies'
                })
        
        return recommendations

    def format_text_report(self, report):
        """Format report as readable text"""
        text = []
        text.append("=" * 80)
        text.append("CONFIDENCE DISTRIBUTION ANALYSIS REPORT")
        text.append("=" * 80)
        text.append(f"Generated: {report['analysis_date']}")
        text.append("")
        
        # Confidence Analysis
        if report['confidence_analysis']:
            conf = report['confidence_analysis']
            text.append("CONFIDENCE ANALYSIS")
            text.append("-" * 40)
            text.append(f"Total Recipes: {conf['total_recipes']}")
            text.append(f"Recipes with Confidence: {conf['recipes_with_confidence']}")
            text.append(f"Coverage: {conf['coverage_percentage']:.1f}%")
            text.append("")
            
            if 'basic_stats' in conf:
                stats = conf['basic_stats']
                text.append("Basic Statistics:")
                text.append(f"  Average Confidence: {stats.get('avg_confidence', 'N/A')}")
                text.append(f"  Min Confidence: {stats.get('min_confidence', 'N/A')}")
                text.append(f"  Max Confidence: {stats.get('max_confidence', 'N/A')}")
                text.append(f"  Standard Deviation: {stats.get('std_confidence', 'N/A')}")
                text.append(f"  Total Individual Scores: {conf.get('total_confidence_scores', 'N/A')}")
                text.append("")
            
            # Add allergen breakdown
            if 'allergen_breakdown' in conf and conf['allergen_breakdown']:
                text.append("Allergen Confidence Breakdown:")
                for allergen, data in conf['allergen_breakdown'].items():
                    text.append(f"  {allergen.title()}: {data['count']} scores, avg: {data['avg_confidence']}, range: {data['min_confidence']}-{data['max_confidence']}")
                text.append("")
            
            if 'range_analysis' in conf:
                text.append("Confidence Range Distribution:")
                for range_info in conf['range_analysis']:
                    text.append(f"  {range_info['range']}: {range_info['count']} ({range_info['percentage']}%)")
                text.append("")
            
            if 'hybrid_analysis' in conf:
                text.append("Hybrid Approach Analysis:")
                for threshold_name, threshold_info in conf['hybrid_analysis'].items():
                    text.append(f"  {threshold_name.replace('_', ' ').title()}: {threshold_info['count']} ({threshold_info['percentage']}%)")
                text.append("")
        
        # Processing Analysis
        if report['processing_analysis']:
            proc = report['processing_analysis']
            text.append("PROCESSING PERFORMANCE ANALYSIS")
            text.append("-" * 40)
            text.append(f"Total Results: {proc['total_results']}")
            text.append(f"Results with Time: {proc['results_with_time']}")
            text.append(f"Coverage: {proc['coverage_percentage']:.1f}%")
            text.append("")
            
            if 'time_stats' in proc:
                stats = proc['time_stats']
                text.append("Processing Time Statistics:")
                text.append(f"  Average Time: {stats.get('avg_time', 'N/A')}s")
                text.append(f"  Min Time: {stats.get('min_time', 'N/A')}s")
                text.append(f"  Max Time: {stats.get('max_time', 'N/A')}s")
                text.append(f"  Standard Deviation: {stats.get('std_time', 'N/A')}s")
                text.append("")
            
            if 'time_range_analysis' in proc:
                text.append("Processing Time Distribution:")
                for range_info in proc['time_range_analysis']:
                    text.append(f"  {range_info['range']}: {range_info['count']} ({range_info['percentage']}%)")
                text.append("")
        
        # Recommendations
        if report['recommendations']:
            text.append("RECOMMENDATIONS")
            text.append("-" * 40)
            for i, rec in enumerate(report['recommendations'], 1):
                text.append(f"{i}. [{rec['priority'].upper()}] {rec['category']}")
                text.append(f"   {rec['recommendation']}")
                text.append(f"   Action: {rec['action']}")
                text.append("")
        
        return "\n".join(text)

    def save_confidence_charts(self, confidence_stats, output_dir):
        """Save confidence distribution charts"""
        if not confidence_stats:
            return
        
        try:
            # Note: Chart generation requires matplotlib and numpy
            # Install with: pip install matplotlib numpy
            self.stdout.write(
                self.style.WARNING('Chart generation requires matplotlib and numpy')
            )
            self.stdout.write('Install with: pip install matplotlib numpy')
            
            # Alternative: Generate text-based charts
            self.generate_text_charts(confidence_stats, output_dir)
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Failed to save charts: {e}')
            )
    
    def generate_text_charts(self, confidence_stats, output_dir):
        """Generate text-based chart representations"""
        if not confidence_stats:
            return
        
        try:
            # Generate text-based histogram
            chart_text = []
            chart_text.append("=" * 60)
            chart_text.append("CONFIDENCE DISTRIBUTION CHARTS (TEXT-BASED)")
            chart_text.append("=" * 60)
            chart_text.append("")
            
            # Range analysis bar chart
            range_data = confidence_stats.get('range_analysis', [])
            if range_data:
                chart_text.append("CONFIDENCE RANGE DISTRIBUTION")
                chart_text.append("-" * 40)
                
                max_count = max(r['count'] for r in range_data) if range_data else 1
                max_bar_length = 50
                
                for range_info in range_data:
                    bar_length = int((range_info['count'] / max_count) * max_bar_length)
                    bar = "█" * bar_length
                    chart_text.append(f"{range_info['range']:<25} | {bar} {range_info['count']} ({range_info['percentage']}%)")
                
                chart_text.append("")
            
            # Hybrid approach analysis
            hybrid_data = confidence_stats.get('hybrid_analysis', {})
            if hybrid_data:
                chart_text.append("HYBRID APPROACH THRESHOLD ANALYSIS")
                chart_text.append("-" * 40)
                
                max_percentage = max(h['percentage'] for h in hybrid_data.values()) if hybrid_data else 1
                max_bar_length = 40
                
                for threshold_name, threshold_info in hybrid_data.items():
                    bar_length = int((threshold_info['percentage'] / max_percentage) * max_bar_length)
                    bar = "█" * bar_length
                    label = threshold_name.replace('_', ' ').title()
                    chart_text.append(f"{label:<25} | {bar} {threshold_info['percentage']}%")
                
                chart_text.append("")
            
            # Save text chart
            chart_path = os.path.join(output_dir, 'confidence_distribution_charts.txt')
            with open(chart_path, 'w') as f:
                f.write('\n'.join(chart_text))
            
            self.stdout.write(f'Text charts saved to: {chart_path}')
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Failed to generate text charts: {e}')
            )

    def display_summary(self, confidence_stats, processing_stats):
        """Display summary of analysis results"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("ANALYSIS SUMMARY")
        self.stdout.write("=" * 60)
        
        if confidence_stats:
            self.stdout.write(f"📊 Confidence Analysis:")
            self.stdout.write(f"   • {confidence_stats['recipes_with_confidence']}/{confidence_stats['total_recipes']} recipes have confidence scores")
            self.stdout.write(f"   • Coverage: {confidence_stats['coverage_percentage']:.1f}%")
            self.stdout.write(f"   • Total individual confidence scores: {confidence_stats.get('total_confidence_scores', 'N/A')}")
            
            if 'basic_stats' in confidence_stats:
                stats = confidence_stats['basic_stats']
                self.stdout.write(f"   • Average confidence: {stats.get('avg_confidence', 'N/A')}")
                self.stdout.write(f"   • Range: {stats.get('min_confidence', 'N/A')} - {stats.get('max_confidence', 'N/A')}")
            
            # Show allergen breakdown summary
            if 'allergen_breakdown' in confidence_stats and confidence_stats['allergen_breakdown']:
                self.stdout.write(f"\n🔍 Allergen Confidence Breakdown:")
                for allergen, data in confidence_stats['allergen_breakdown'].items():
                    self.stdout.write(f"   • {allergen.title()}: {data['count']} scores, avg: {data['avg_confidence']}")
        
        if processing_stats:
            self.stdout.write(f"\n⏱️  Processing Performance:")
            self.stdout.write(f"   • {processing_stats['results_with_time']}/{processing_stats['total_results']} results have timing data")
            self.stdout.write(f"   • Coverage: {processing_stats['coverage_percentage']:.1f}%")
            
            if 'time_stats' in processing_stats:
                stats = processing_stats['time_stats']
                self.stdout.write(f"   • Average processing time: {stats.get('avg_time', 'N/A')}s")
        
        self.stdout.write("\n📁 Reports saved to 'output' directory")
        self.stdout.write("💡 Use --save-charts to generate visualizations")
        self.stdout.write("🔍 Use --detailed for comprehensive statistics")
